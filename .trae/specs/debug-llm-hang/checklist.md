# Checklist

- [ ] `test_llm_connection.py` runs successfully and returns a response from the LLM.
- [ ] If `test_llm_connection.py` fails, the error message clearly indicates connection refused, timeout, or auth error.
- [ ] `verify_refinement.py` output shows exactly what text is being sent to the model before it hangs.
- [ ] Logs distinguish between "preparing request" and "waiting for response".
