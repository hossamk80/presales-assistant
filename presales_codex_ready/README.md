# IMDAD Pre-Sales Assistant

Streamlit application for RFP analysis, compliance matrix, BOQ review, and technical proposal generation.

## Run

```bash
cd imdad
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## Main entry point

```text
imdad/app.py
```

## Notes

- Add your Google Gemini API key from the app settings page.
- Current AI provider implemented: Google Gemini.
- OpenAI and Claude fields are placeholders only.
