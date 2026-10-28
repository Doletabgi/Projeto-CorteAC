"""
tests/test_nesting_backend.py - Testes unitários para a arquitetura de backends de Nesting

Valida:
1. PythonBackend.nest_sheet como referência de ouro.
2. NfpBackend.nest_sheet com 50 peças reais (zero colisões estritas com polygons_collide).
3. Concordância de posições: >= 80% das peças com coordenadas dentro de 1.0mm de tolerância.
4. Seleção de backend via variável de ambiente CORTEAC_BACKEND.
5. Fallback automático transparente para PythonBackend em caso de exceção.
"""

import math
import os
from unittest.mock import patch
import pytest

from cad.geometry import polygons_collide
from cad.nesting_backend import (
    NestingBackend,
    NfpBackend,
    PythonBackend,
    get_nesting_backend,
)
from tools.bench_nest import load_benchmark_shapes


def test_python_backend_reference():
    """Valida o funcionamento do backend Python padrão como referência de ouro."""
    shapes = load_benchmark_shapes(10)
    backend = PythonBackend()
    placed = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=10,
        strategy="flashnestsheet",
        params="stdNOTFill",
        gap_mm=1.0,
    )
    assert len(placed) == 10
    for p in placed:
        assert "poly" in p
        assert "bbox" in p
        assert "x" in p
        assert "y" in p


def test_nfp_backend_zero_collision_50_pieces():
    """Valida que o NfpBackend posiciona 50 peças reais com ZERO colisão estrita."""
    shapes = load_benchmark_shapes(50)
    backend = NfpBackend()
    placed = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=50,
        strategy="flashnestsheet",
        params="ALTERNADO",
        gap_mm=1.0,
    )
    assert len(placed) == 50

    # Verificação cruzada O(N^2) de zero colisão com gap industrial estrito
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            p_a = placed[i]
            p_b = placed[j]
            col = polygons_collide(
                p_a["poly"],
                p_b["poly"],
                gap=1.0,
                bbox_a=p_a["bbox"],
                bbox_b=p_b["bbox"],
            )
            assert not col, f"Colisão detectada entre peça {p_a['id']} e {p_b['id']} no NfpBackend"


def test_backend_coordinate_agreement():
    """
    Testa a concordância geométrica de posições entre PythonBackend e NfpBackend.
    Meta estrita: >= 80% das peças com distância euclidiana <= 1.0 mm.
    """
    shapes = load_benchmark_shapes(50)
    py_backend = PythonBackend()
    nfp_backend = NfpBackend()

    placed_py = py_backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=50,
        strategy="flashnestsheet",
        params="ALTERNADO",
        gap_mm=1.0,
    )

    placed_nfp = nfp_backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=50,
        strategy="flashnestsheet",
        params="ALTERNADO",
        gap_mm=1.0,
    )

    assert len(placed_py) == len(placed_nfp) == 50

    matches = 0
    total = len(placed_py)
    for i in range(total):
        p_py = placed_py[i]
        p_nfp = placed_nfp[i]
        dist = math.hypot(p_py["x"] - p_nfp["x"], p_py["y"] - p_nfp["y"])
        if dist <= 1.0:
            matches += 1

    agreement_pct = (matches / total) * 100.0
    assert agreement_pct >= 80.0, f"Concordância foi {agreement_pct:.1f}% (esperado >= 80.0%)"


def test_get_nesting_backend_env_var(monkeypatch):
    """Testa a seleção dinâmica de backend via CORTEAC_BACKEND."""
    # Padrão sem variável definida -> NfpBackend (promovido na Fase 4)
    monkeypatch.delenv("CORTEAC_BACKEND", raising=False)
    backend = get_nesting_backend()
    assert isinstance(backend, NfpBackend)

    # Rollback garantido: CORTEAC_BACKEND="python" -> PythonBackend
    monkeypatch.setenv("CORTEAC_BACKEND", "python")
    backend = get_nesting_backend()
    assert isinstance(backend, PythonBackend)

    # CORTEAC_BACKEND="nfp" -> NfpBackend
    monkeypatch.setenv("CORTEAC_BACKEND", "nfp")
    backend = get_nesting_backend()
    assert isinstance(backend, NfpBackend)

    # Chamada explícita por parâmetro
    assert isinstance(get_nesting_backend("nfp"), NfpBackend)
    assert isinstance(get_nesting_backend("python"), PythonBackend)


def test_nfp_backend_automatic_fallback(caplog):
    """
    Testa se o NfpBackend cai graciosamente de volta para o PythonBackend
    caso ocorra uma exceção interna no motor analítico.
    """
    shapes = load_benchmark_shapes(10)
    backend = NfpBackend()

    # Mocka uma falha interna proposital em _nest_sheet_nfp
    with patch.object(backend, "_nest_sheet_nfp", side_effect=RuntimeError("Simulated NFP crash")):
        placed = backend.nest_sheet(
            available_shapes=shapes,
            bed_width_mm=2000.0,
            bed_height_mm=1200.0,
            target_count=10,
            strategy="flashnestsheet",
            params="stdNOTFill",
            gap_mm=1.0,
        )

        # Deve completar normalmente via fallback do PythonBackend
        assert len(placed) == 10
        # Deve ter logado o warning de fallback
        assert any("fallback automático para PythonBackend" in record.message for record in caplog.records)


def test_nfp_backend_sanity_flag(monkeypatch):
    """Testa que NfpBackend funciona tanto com CORTEAC_NFP_SANITY='0' quanto '1'."""
    shapes = load_benchmark_shapes(20)
    backend = NfpBackend()

    monkeypatch.setenv("CORTEAC_NFP_SANITY", "0")
    placed_fast = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=20,
        strategy="flashnestsheet",
        params="stdNOTFill",
        gap_mm=1.0,
    )

    monkeypatch.setenv("CORTEAC_NFP_SANITY", "1")
    placed_sanity = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=20,
        strategy="flashnestsheet",
        params="stdNOTFill",
        gap_mm=1.0,
    )

    assert len(placed_fast) == len(placed_sanity) == 20
    for p1, p2 in zip(placed_fast, placed_sanity):
        assert abs(p1["x"] - p2["x"]) < 1e-3
        assert abs(p1["y"] - p2["y"]) < 1e-3


def test_nfp_backend_zero_collision_300_pieces():
    """Valida que o NfpBackend posiciona 300 peças reais (chapa cheia) com ZERO colisão."""
    shapes = load_benchmark_shapes(300)
    backend = NfpBackend()
    placed = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=2000.0,
        bed_height_mm=1200.0,
        target_count=300,
        strategy="flashnestsheet",
        params="ALTERNADO",
        gap_mm=1.0,
    )
    assert len(placed) > 0

    # Verificação cruzada O(N^2) de zero colisão
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            p_a = placed[i]
            p_b = placed[j]
            col = polygons_collide(
                p_a["poly"],
                p_b["poly"],
                gap=1.0,
                bbox_a=p_a["bbox"],
                bbox_b=p_b["bbox"],
            )
            assert not col, f"Colisão detectada entre peça {p_a['id']} e {p_b['id']} no NfpBackend"


def test_nfp_backend_zero_collision_500_pieces():
    """Valida que o NfpBackend posiciona 500 peças reais (chapa expandida) com ZERO colisão."""
    shapes = load_benchmark_shapes(500)
    backend = NfpBackend()
    placed = backend.nest_sheet(
        available_shapes=shapes,
        bed_width_mm=3000.0,
        bed_height_mm=2000.0,
        target_count=500,
        strategy="flashnestsheet",
        params="ALTERNADO",
        gap_mm=1.0,
    )
    assert len(placed) > 0

    # Verificação cruzada O(N^2) de zero colisão
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            p_a = placed[i]
            p_b = placed[j]
            col = polygons_collide(
                p_a["poly"],
                p_b["poly"],
                gap=1.0,
                bbox_a=p_a["bbox"],
                bbox_b=p_b["bbox"],
            )
            assert not col, f"Colisão detectada entre peça {p_a['id']} e {p_b['id']} no NfpBackend"


