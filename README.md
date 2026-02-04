# Amélie 👁️🌸

A **Amélie** é uma assistente multimodal de audiodescrição desenvolvida para promover a acessibilidade de pessoas com deficiência visual. Utilizando a inteligência do Google Gemini, ela transforma fotos, vídeos, áudios e documentos em descrições detalhadas e acessíveis via Telegram.

## 🚀 Como Rodar (via Docker)

A forma mais simples e recomendada de rodar a Amélie é utilizando Docker.

### Pré-requisitos
- Docker e Docker Compose instalados.
- Um token de bot do Telegram (via [@BotFather](https://t.me/botfather)).
- Uma chave de API do Google Gemini (via [Google AI Studio](https://aistudio.google.com/)).

### Passo a Passo

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/vision-bot.git
   cd vision-bot
   ```

2. **Configure as variáveis de ambiente:**
   Copie o arquivo de exemplo e preencha com suas chaves:
   ```bash
   cp .env.example .env
   nano .env
   ```

3. **Suba o container:**
   ```bash
   docker compose up -d --build
   ```

A Amélie agora está no ar! Você pode acompanhar os logs com:
```bash
docker compose logs -f
```

## 🛠️ Comandos Suportados
- `/start` - Inicia o bot e apresenta os termos de privacidade.
- `/ajuda` - Exibe o manual de uso.
- `/curto` | `/longo` - Define o nível de detalhamento das imagens.
- `/legenda` | `/completo` - Define o modo de análise de vídeos.

## 🔒 Privacidade e Acessibilidade
- **Cegueira do Gestor:** Arquivos são processados e deletados imediatamente após a resposta.
- **Texto Puro:** Todas as respostas são limpas de Markdown complexo para garantir fluidez em leitores de tela (TalkBack/NVDA).
- **Sem Memória:** Para garantir a privacidade, a Amélie não mantém histórico de conversas anteriores; cada mídia é tratada como um evento único.

## 🏗️ Arquitetura
O projeto utiliza **Arquitetura Hexagonal**, permitindo que a inteligência central seja independente de adaptadores externos como o Telegram ou o SQLite.

---
*Amélie: Enxergando a beleza nos pequenos detalhes.*
