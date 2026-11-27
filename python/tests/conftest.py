import pytest


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path_factory):
    """No test may read or write the real ~/.config/mechbase/config.json (it holds the user's token),
    nor pick up a token exported in the developer's shell."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    for var in ("MECHBASE_TOKEN", "MECHBASE_URL", "MECHBASE_INSTALLATION"):
        monkeypatch.delenv(var, raising=False)
