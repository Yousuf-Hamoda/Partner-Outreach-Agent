# Partner Outreach Agent

AI-powered outreach agent that reads a CSV of potential partners and drafts personalized emails using GPT-4o.

## Setup

```bash
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4o"
```

## Usage

```bash
# Dry-run with built-in sample data (no emails sent)
python main.py

# Use LangChain instead of raw OpenAI client
python main.py --use-langchai

# Your own CSV, still dry-run
python main.py --csv partners.csv

# Actually send via SMTP
export SMTP_USERNAME="you@gmail.com"
export SMTP_PASSWORD="your-app-password"   # Gmail: use an App Password
python main.py --csv partners.csv --send

# Custom output file
python main.py --csv partners.csv --output my_results.csv

# LangChain + send mode
python main.py --csv partners.csv --use-langchain --send
```

## Email generation backends
 
The agent supports two backends for email generation:
 
| Backend | Flag | Description |
|---------|------|-------------|
| **Pure OpenAI** | (default) | Raw `openai` Python client with manual prompt building and JSON parsing |
| **LangChain** | `--use-langchain` | Uses LangChain's `ChatOpenAI` + prompt templates + structured output parser |

## Input CSV format

| Column     | Required | Description              |
|------------|----------|--------------------------|
| `name`     | ✓        | Partner's full name      |
| `email`    | ✓        | Their email address      |
| `industry` | ✓        | Industry/vertical        |
| `website`  |          | Company website (optional)|

## Configuration

Edit the `MY_COMPANY` block at the top of `main.py`:

```python
MY_COMPANY = Company(
    name="Acme Corp",
    sender_name="Alex Chen",
    sender_role="Partnerships Manager",
    sender_email="alex@acmecorp.com",
    value_proposition="...",
)
```

## SMTP environment variables

| Variable        | Default          | Notes                          |
|----------------|------------------|--------------------------------|
| `SMTP_HOST`     | smtp.gmail.com   |                                |
| `SMTP_PORT`     | 587              | TLS port                       |
| `SMTP_USERNAME` | —                | Required for `--send`          |
| `SMTP_PASSWORD` | —                | Use a Gmail App Password       |
