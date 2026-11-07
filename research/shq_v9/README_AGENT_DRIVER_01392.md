# Agent Driver 01392

Fills PR#12 gap: `method_registry.json` + `shq_agent_driver.py` callable dispatch.

```bash
python3 validate_registry.py method_registry.json
python3 shq_agent_driver.py selftest
python3 shq_agent_driver.py run-full --src SRC --empty EMPTY --out /tmp/run
```

Not production `src/ige`. ACCEPT_FULL_HD=false.
