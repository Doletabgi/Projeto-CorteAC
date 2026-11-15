"""Conversa guiada de diagnóstico baseada nos dados locais da sessão."""

import tkinter as tk
from tkinter import ttk
import unicodedata

from config import THEME
from ui.icon_widgets import IconButton


class DiagnosticAssistant(tk.Frame):
    SECTIONS = {"materials": "Materiais", "shapes": "Moldes", "general": "Geral", "layouts": "Layout"}
    STEPS = ("Entender o problema", "Conferir a sessão", "Orientar a solução", "Concluir")

    def __init__(self, parent, *, analyze, open_section, clear_memory, save_report, test_performance):
        super().__init__(parent, bg=THEME["bg_card"], padx=12, pady=10)
        self.analyze = analyze
        self.open_section = open_section
        self.clear_memory = clear_memory
        self.save_report = save_report
        self.test_performance = test_performance
        self.history = []
        self.phase = "welcome"
        self.issue = "check"
        self.awaiting_return = False
        self._state = None

        heading = tk.Frame(self, bg="#e8eff7", padx=12, pady=10)
        heading.pack(fill="x", pady=(0, 10))
        tk.Label(heading, text="OC", bg="#244c77", fg="white", font=("Segoe UI", 14, "bold"), padx=10, pady=8).pack(side="left", padx=(0, 12))
        tk.Label(heading, text="Assistente OpenCorte", bg="#e8eff7", fg="#183b60", font=("Segoe UI", 12, "bold"), anchor="w").pack(fill="x")
        self.lbl_session = tk.Label(heading, text="Vou orientar você usando os dados desta sessão.", bg="#e8eff7", fg="#365675", font=("Segoe UI", 9), anchor="w", wraplength=600, justify="left")
        self.lbl_session.pack(fill="x", pady=(3, 0))
        self.lbl_step = tk.Label(self, bg=THEME["bg_card"], fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w")
        self.lbl_step.pack(fill="x")
        ttk.Style(self).configure("Diagnostic.Horizontal.TProgressbar", thickness=6)
        self.progress = ttk.Progressbar(self, mode="determinate", maximum=4, style="Diagnostic.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(5, 10))

        conversation = tk.Frame(self, bg=THEME["bg_input"], relief="sunken", bd=1)
        self.transcript = tk.Text(conversation, wrap="word", state="disabled", height=10, width=60,
                                  bg=THEME["bg_input"], fg=THEME["text_main"], font=("Segoe UI", 10),
                                  relief="flat", padx=14, pady=10, cursor="arrow")
        scroll = ttk.Scrollbar(conversation, orient="vertical", command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scroll.set)
        self.transcript.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.transcript.tag_configure("assistant_name", foreground="#244c77", font=("Segoe UI", 9, "bold"), spacing1=8)
        self.transcript.tag_configure("user_name", foreground="#555555", font=("Segoe UI", 9, "bold"), spacing1=8)
        self.transcript.tag_configure("assistant", background="#eef4fa", lmargin1=8, lmargin2=8, rmargin=8, spacing1=5, spacing3=8)
        self.transcript.tag_configure("user", background="#f1f1f1", lmargin1=8, lmargin2=8, rmargin=8, spacing1=5, spacing3=8)

        bottom = tk.Frame(self, bg=THEME["bg_card"])
        bottom.pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(bottom, text="Escreva o que aconteceu ou use uma das respostas acima:", bg=THEME["bg_card"],
                 fg=THEME["text_main"], font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0, 4))
        entry_row = tk.Frame(bottom, bg=THEME["bg_card"])
        entry_row.pack(fill="x")
        self.entry = tk.Entry(entry_row, font=("Segoe UI", 10), relief="sunken", bd=1)
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry.bind("<Return>", self._submit_entry)
        self._button(entry_row, "Enviar", self._submit_entry).pack(side="left", padx=(8, 0))
        tools = tk.Frame(bottom, bg=THEME["bg_card"])
        tools.pack(fill="x", pady=(8, 0))
        self._button(tools, "Recomeçar conversa", self.restart).pack(side="left")
        self._button(tools, "Salvar conversa e relatório…", self._save_report).pack(side="right")
        self.replies = tk.Frame(self, bg=THEME["bg_card"])
        self.replies.pack(side="bottom", fill="x", pady=(10, 0))
        conversation.pack(fill="both", expand=True)
        self.restart()

    def _button(self, parent, text, callback):
        return IconButton(parent, text=text, command=callback, font=("Segoe UI", 9),
                          bg=THEME["bg_surface"], fg=THEME["text_main"], padx=8, pady=5, cursor="hand2")

    def _step(self, index):
        self.lbl_step.config(text=f"Etapa {index} de 4 · {self.STEPS[index - 1]}")
        self.progress["value"] = index

    def _say(self, text, role="assistant"):
        self.history.append({"role": role, "text": text})
        self.transcript.config(state="normal")
        start = self.transcript.index("end-1c")
        self.transcript.insert("end", "Assistente\n" if role == "assistant" else "Você\n", role + "_name")
        self.transcript.insert("end", text + "\n", role)
        self.transcript.insert("end", "\n")
        self.transcript.config(state="disabled")
        self.transcript.see("end")
        self.transcript.see(start)

    def _choices(self, choices):
        for child in self.replies.winfo_children():
            child.destroy()
        for index, (label, action) in enumerate(choices):
            self._button(self.replies, label, lambda label=label, action=action: self.choose(label, action)).grid(
                row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=3)
        self.replies.columnconfigure(0, weight=1)
        self.replies.columnconfigure(1, weight=1)

    def restart(self):
        self.history.clear()
        self.transcript.config(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.config(state="disabled")
        self.entry.delete(0, "end")
        self.phase, self.issue, self.awaiting_return = "welcome", "check", False
        self._step(1)
        self._say("Olá! Vou ajudar você a conferir o trabalho e encontrar o próximo passo. O que está acontecendo?")
        self._welcome_choices()

    def _welcome_choices(self):
        self._choices([("Não consigo gerar o encaixe", "generate"), ("O cálculo está lento", "slow"),
                       ("Quero conferir a sessão", "check"), ("Preciso falar com o suporte", "support")])

    def _submit_entry(self, event=None):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.respond(text)
        return "break"

    @staticmethod
    def _normalize(text):
        return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")

    def respond(self, text):
        self._say(text, "user")
        normalized = self._normalize(text)
        if self.phase == "details":
            self._prepare_report()
        elif normalized in ("funcionou", "resolveu", "resolvido", "deu certo") or (normalized == "sim" and self.phase == "resolution"):
            self._finish()
        elif any(word in normalized for word in ("lent", "demor", "trav")):
            self._start("slow")
        elif any(word in normalized for word in ("sobrepos", "colis", "fora da placa", "pecas fora")):
            self._start("layout")
        elif any(word in normalized for word in ("suporte", "relatorio", "ajuda")):
            self._ask_details()
        elif any(word in normalized for word in ("gerar", "gera", "encaix", "erro")):
            self._start("generate")
        elif any(word in normalized for word in ("confer", "verific", "ajustei", "voltei", "pronto")):
            self._start(self.issue if self.issue in ("check", "generate", "layout") else "check")
        elif normalized in ("nao", "nao funcionou", "continua igual"):
            self._ask_details()
        else:
            self._say("Anotei sua descrição. Para orientar você, escolha a situação que mais se aproxima do problema. Se houver uma mensagem de erro, podemos incluí-la no relatório para o suporte.")
            self._welcome_choices()

    def choose(self, label, action):
        self._say(label, "user")
        if action in ("check", "generate", "slow", "layout"):
            self._start(action)
        elif action.startswith("open:"):
            self.awaiting_return = True
            section = action.split(":", 1)[1]
            self._say(f"Vou abrir {self.SECTIONS[section]}. Faça a conferência e depois volte pelo menu Ferramentas → Debug / Diagnóstico. Vou reler os dados quando você voltar.")
            if self.open_section:
                self.open_section(section)
        elif action == "recheck":
            self._start(self.issue)
        elif action == "clear":
            if self.clear_memory():
                self._say("Memória temporária liberada. Seus dados foram mantidos. Volte à aba Geral e tente Gerar novamente. Funcionou?")
                self.phase = "resolution"
                self._step(3)
                self._choices([("Voltar à sessão", "open:general"), ("Sim, funcionou", "resolved"),
                               ("Continua com problema", "unresolved")])
            else:
                self._say("Não consegui concluir a liberação agora. Veja a mensagem no rodapé. Aguarde qualquer cálculo ou teste em andamento e tente novamente.")
                self._choices([("Tentar novamente", "clear"), ("Preparar relatório", "support")])
        elif action == "support" or action == "unresolved":
            self._ask_details()
        elif action == "save":
            self._save_report()
        elif action == "resolved":
            self._finish()
        elif action == "test":
            previous_phase = self.phase
            self.phase = "testing"
            if self.test_performance():
                if self.phase == "testing":
                    self._say("O teste está em andamento com peças de exemplo. Avisarei aqui quando terminar; você pode continuar lendo a conversa.")
                    self._choices([("Preparar relatório para suporte", "support")])
            else:
                self.phase = previous_phase
                self._say("O teste não foi iniciado. Se você cancelou a escolha do arquivo, pode tentar novamente. Se há um cálculo em andamento, aguarde o término; veja a mensagem no rodapé.")

    def _read_session(self):
        self._step(2)
        self._state = self.analyze()
        if self._state is None:
            self._say("Não consegui ler os dados desta sessão. Veja a mensagem no rodapé e tente verificar novamente.")
            self._choices([("Verificar novamente", "recheck"), ("Recomeçar", "check")])
            return False
        return True

    def _start(self, issue):
        self.issue = issue
        self.phase = "guidance"
        if not self._read_session():
            return
        context, checks = self._state["context"], self._state["checks"]
        if context.get("nesting_in_progress"):
            self._say("Há um encaixe sendo calculado. Aguarde o término para avaliar o resultado. Evite iniciar outra geração durante esse cálculo.")
            self._choices([("Já terminou, verificar", "recheck"), ("Preparar relatório", "support")])
            return
        self._step(3)
        if issue == "slow":
            self._say("A demora acontece desde o primeiro cálculo ou apareceu depois de gerar vários encaixes?")
            self._choices([("Depois de vários cálculos: liberar memória", "clear"),
                           ("Desde o início: testar com exemplos", "test"),
                           ("Conferir quantidades e material", "check"), ("Preparar relatório", "support")])
            return
        pending = [check for check in checks if check["status"] == "attention"]
        if pending:
            first = pending[0]
            self._say(f"Encontrei {len(pending)} ponto(s) para ajustar. Vamos começar por {first['title'].lower()}: {first['result']}.\n\n{first['guidance']}")
            self._choices([(f"Abrir {self.SECTIONS[first['target']]}", "open:" + first["target"]),
                           ("Já ajustei, verificar novamente", "recheck"), ("Preciso de ajuda com esse ajuste", "support")])
        elif issue == "layout":
            target = "layouts" if context.get("placed_count") else "general"
            self._say("Os dados básicos estão preenchidos. Esta análise não examina colisões entre as peças. Abra Layout para revisar as posições; se ainda não há encaixe, use Gerar na aba Geral primeiro.")
            self._choices([(f"Abrir {self.SECTIONS[target]}", "open:" + target), ("Preparar relatório", "support")])
        elif not context.get("placed_count"):
            self._say("Os dados básicos estão preenchidos e ainda não há peças posicionadas. Abra a aba Geral e clique em Gerar. Depois volte para conferir o resultado.")
            self._choices([("Abrir Geral", "open:general"), ("Já gerei, conferir resultado", "recheck"),
                           ("Aparece uma mensagem de erro", "support")])
        else:
            self.phase = "resolution"
            self._say("Os dados básicos estão preenchidos e há peças no layout. Abra Layout para revisar o resultado. O problema que você percebeu foi resolvido?")
            self._choices([("Abrir Layout", "open:layouts"), ("Sim, funcionou", "resolved"),
                           ("Ainda preciso de ajuda", "unresolved")])

    def on_reopen(self):
        if self.awaiting_return:
            self.awaiting_return = False
            self._say("Você voltou. Vou conferir os dados atuais da sessão.")
            if self.phase == "resolution":
                self._say("Depois de tentar gerar novamente, o cálculo melhorou?")
                self._choices([("Sim, funcionou", "resolved"), ("Continua lento", "slow"), ("Preparar relatório", "support")])
            else:
                self._start(self.issue)

    def _ask_details(self):
        if self.phase == "welcome":
            self.issue = "support"
        self.phase = "details"
        self._step(3)
        self._say("Descreva abaixo o que aconteceu e, se apareceu um erro, copie a mensagem. Vou juntar essa descrição às verificações da sessão.")
        self._choices([("Preparar relatório sem acrescentar descrição", "save")])
        self.entry.focus_set()

    def _prepare_report(self):
        self.phase = "report"
        self._step(4)
        self._say("Sua descrição foi registrada nesta conversa. Posso salvar a conversa e os dados atuais da sessão em um arquivo para você enviar ao suporte.")
        self._choices([("Salvar conversa e relatório", "save"), ("Conferir sessão novamente", "check")])

    def _save_report(self):
        path = self.save_report()
        if path:
            self.phase = "report_saved"
            self._step(4)
            self._say(f"Relatório salvo em:\n{path}\n\nEnvie esse arquivo ao suporte. A conversa foi incluída.")
            self._choices([("Conferir sessão novamente", "check"), ("O problema foi resolvido", "resolved")])

    def _finish(self):
        self.phase = "complete"
        self._step(4)
        self._say("Você informou que o problema foi resolvido. Pode continuar o trabalho. Se precisar, salve esta conversa ou comece uma nova orientação.")
        self._choices([("Conferir a sessão novamente", "check"), ("Salvar conversa", "save")])

    def benchmark_finished(self, success, detail):
        if success:
            self._say(f"O teste com peças de exemplo terminou. O relatório de desempenho está em:\n{detail}\n\nEsse teste não recalcula sua sessão. Se a lentidão continuar, inclua esse arquivo no contato com o suporte.")
        else:
            self._say(f"O teste de desempenho não terminou: {detail}. Podemos registrar esse resultado para o suporte.")
        if self.phase == "testing":
            self.phase = "test_complete"
            self._step(3)
            self._choices([("Voltar à sessão", "open:general"), ("Preparar relatório para suporte", "support")])
