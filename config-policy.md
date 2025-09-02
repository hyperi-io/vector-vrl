# Config Policy

Never hardcode values. Use dynaconf for Python.

**Precedence:** CLI → ENV → .env → config file → code default

**Setup:**
```python
from dynaconf import Dynaconf
settings = Dynaconf(envvar_prefix="APP", settings_files=['config/*.yaml'], load_dotenv=True)
```

**Convention:** `config/default.yaml` + `config/{env}.yaml`
K8s mounts ConfigMaps to `/app/config/`

Deploy to K8s/Helm. ENV vars use `APP_` prefix.