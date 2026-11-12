# Setup simplificado: local ou rede

O instalador Windows oferece duas opções: **Instalar localmente** e
**Usar um servidor na rede**. O modo local dispensa endereço; o modo de rede
mostra um único campo, em vez dos três anteriores.

| Endereço informado | Servidor MySQL | Moldes | Sessões |
|---|---|---|---|
| `SERVIDOR` | `SERVIDOR` | `\\SERVIDOR\Fabrica\Moldes` | `\\SERVIDOR\Fabrica\Sessoes` |
| `192.168.1.100` | `192.168.1.100` | `\\192.168.1.100\Fabrica\Moldes` | `\\192.168.1.100\Fabrica\Sessoes` |
| `\\SERVIDOR\Producao` | `SERVIDOR` | `\\SERVIDOR\Producao\Moldes` | `\\SERVIDOR\Producao\Sessoes` |

O servidor deve oferecer MySQL e o compartilhamento informado com permissão
para os operadores. O setup configura o cliente; não instala MySQL nem cria
compartilhamentos no servidor. Pastas mapeadas (Z:) não identificam o servidor:
nesse assistente, use o nome/IP ou o caminho UNC equivalente.

A escolha local usa `jobmanager.db` na instalação e limpa os caminhos de rede
do `db.ini`. Nenhum banco existente é apagado ou transferido. Trocar o modo
não migra os dados entre o banco central e o local.

Em atualizações, o setup lê o `db.ini` existente e mantém o arquivo intacto
se a opção e o endereço não forem alterados, inclusive configurações antigas
com caminhos personalizados. Quando o endereço muda, preserva porta, usuário,
senha, nome do banco e outras opções existentes. Instalações novas em rede usam
os parâmetros padrão de fábrica já adotados pelo projeto. Configurações
específicas do banco continuam disponíveis na tela de conexão do aplicativo.

O setup chama o próprio executável com `--configurar-instalacao`; a lógica fica
em `db/installation_settings.py`. A gravação do INI é atômica e não se conecta ao
banco. Falhas de gravação interrompem a conclusão do setup com uma mensagem.
O atualizador central inclui os testes desse caminho em toda build.

Os controles e eventos do assistente seguem a
[documentação oficial do Inno Setup](https://jrsoftware.org/ishelp/topic_scriptevents.htm).
