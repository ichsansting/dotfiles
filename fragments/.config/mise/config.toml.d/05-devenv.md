settings.idiomatic_version_file_enable_tools = ["python", "terraform"]
settings.auto_install = true
settings.python.uv_venv_auto = "source"
settings.pipx.uvx = true

env.UV_PYTHON.value = "{{ tools.python.path }}"
env.UV_PYTHON.tools = true
