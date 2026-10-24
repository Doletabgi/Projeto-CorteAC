"""
JobManager 2000 (Python Edition)
CAM / CAD: Biblioteca de Compressão e Descompressão CZLIB (Comelz)
Implementação pura em Python 3.12 (compatível com CZLIB v1 e v2).

Especificação Técnica:
- Magic: 6 bytes ('CZLIB\x01' para gzip legado ou 'CZLIB\x02' para bzip2 modificado).
- Em CZLIB v2, o fluxo bzip2 omite os 10 bytes iniciais ('BZh91AY&SY') na gravação.
- Na leitura de CZLIB v2, esses 10 bytes são reinjetados antes de descomprimir.
"""

import bz2
import gzip
import io
from typing import Union, BinaryIO

CZLIB_V1_MAGIC = b"CZLIB"
CZLIB_V2_MAGIC = b"CZLIB"
BZIP2_HEADER = b"BZh91AY&SY"


class CZLIBError(Exception):
    """Erro de validação ou processamento do container CZLIB."""
    pass


def decompress_czlib(data: Union[bytes, bytearray, BinaryIO]) -> bytes:
    """
    Descomprime dados binários no formato proprietário Comelz CZLIB (v1 ou v2).
    Retorna os bytes descomprimidos (geralmente XML UTF-8).
    """
    if hasattr(data, "read"):
        raw_bytes = data.read()
    else:
        raw_bytes = bytes(data)

    if len(raw_bytes) < 6:
        raise CZLIBError("Tamanho de dados insuficiente para cabeçalho CZLIB (mínimo 6 bytes).")

    magic = raw_bytes[:6]

    if magic == CZLIB_V2_MAGIC:
        try:
            decompressor = bz2.BZ2Decompressor()
            # Reinjeta o cabeçalho padrão de 10 bytes omitido pela Comelz
            res = decompressor.decompress(BZIP2_HEADER)
            res += decompressor.decompress(raw_bytes[6:])
            return res
        except Exception as e:
            raise CZLIBError(f"Falha ao descomprimir stream CZLIB v2 (bzip2): {e}") from e

    elif magic == CZLIB_V1_MAGIC:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes[6:]), mode="rb") as gz:
                return gz.read()
        except Exception as e:
            raise CZLIBError(f"Falha ao descomprimir stream CZLIB v1 (gzip): {e}") from e

    else:
        if raw_bytes[:5] == b"CZLIB":
            ver = raw_bytes[5]
            raise CZLIBError(f"Versão CZLIB não suportada: {ver}")
        raise CZLIBError(f"Assinatura CZLIB inválida: esperava 'CZLIB\x02', obteve {magic!r}")


def compress_czlib(data: Union[bytes, str], version: int = 2, compresslevel: int = 9) -> bytes:
    """
    Comprime dados (bytes ou string UTF-8) no container proprietário Comelz CZLIB.
    Por padrão utiliza a versão 2 (BZIP2 modificado, padrão das máquinas Comelz modernas).
    """
    if isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = bytes(data)

    if version == 2:
        compressor = bz2.BZ2Compressor(compresslevel)
        compressed = compressor.compress(payload) + compressor.flush()

        # O bzip2 padrão sempre inicia com b'BZh91AY&SY' (10 bytes com compresslevel 9)
        # Em níveis diferentes pode variar o caractere de bloco (ex: BZh1..BZh9)
        if compressed.startswith(b"BZh") and len(compressed) >= 10:
            compressed_body = compressed[10:]
        else:
            compressed_body = compressed

        return CZLIB_V2_MAGIC + compressed_body

    elif version == 1:
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=compresslevel) as gz:
            gz.write(payload)
        return CZLIB_V1_MAGIC + buf.getvalue()

    else:
        raise ValueError(f"Versão CZLIB inválida: {version}. Deve ser 1 ou 2.")
