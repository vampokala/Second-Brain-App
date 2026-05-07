import os
import tempfile

import pytest
import yaml
from src.utils.config import Config, doc_ollama_runtime_enabled, load_config, provider_api_key_env


def _write_config(data: dict) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(data, f)
    f.close()
    return f.name


class TestConfigDefaults:
    def test_default_values(self):
        cfg = Config()
        assert cfg.chunk_size == 600
        assert cfg.overlap == 100
        assert cfg.chunk_tokenizer == "gpt2"
        assert cfg.log_level == "INFO"

    def test_custom_values(self):
        cfg = Config(chunk_size=500, overlap=50)
        assert cfg.chunk_size == 500
        assert cfg.overlap == 50

    def test_llm_defaults_present(self):
        cfg = Config()
        assert cfg.llm.default_provider == "ollama"
        assert "ollama" in cfg.llm.allowed_models_by_provider


class TestLoadConfig:
    def test_loads_yaml_values(self):
        path = _write_config({"chunk_size": 512, "overlap": 64})
        try:
            cfg = load_config(path)
            assert cfg.chunk_size == 512
            assert cfg.overlap == 64
        finally:
            os.unlink(path)

    def test_missing_keys_use_defaults(self):
        path = _write_config({"chunk_size": 256})
        try:
            cfg = load_config(path)
            assert cfg.overlap == 100  # default
        finally:
            os.unlink(path)

    def test_empty_yaml_uses_all_defaults(self):
        path = _write_config({})
        try:
            cfg = load_config(path)
            assert cfg.chunk_size == 600
        finally:
            os.unlink(path)

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yaml")

    def test_invalid_value_raises(self):
        path = _write_config({"chunk_size": "not_an_int"})
        try:
            with pytest.raises((ValueError, Exception)):
                load_config(path)
        finally:
            os.unlink(path)

    def test_env_override(self, monkeypatch):
        path = _write_config({"chunk_size": 100})
        monkeypatch.setenv("CHUNK_SIZE", "999")
        try:
            cfg = load_config(path)
            assert cfg.chunk_size == 999
        finally:
            os.unlink(path)

    def test_env_specific_config_merged(self):
        base_path = _write_config({"chunk_size": 100, "log_level": "INFO"})
        # write a .test.yaml override next to the base config
        base, ext = os.path.splitext(base_path)
        env_path = f"{base}.test{ext}"
        try:
            with open(env_path, "w") as f:
                yaml.dump({"log_level": "DEBUG"}, f)
            cfg = load_config(base_path, env="test")
            assert cfg.chunk_size == 100   # from base
            assert cfg.log_level == "DEBUG"  # from env override
        finally:
            os.unlink(base_path)
            if os.path.exists(env_path):
                os.unlink(env_path)


def test_provider_api_key_env():
    assert provider_api_key_env("openai") == "OPENAI_API_KEY"
    assert provider_api_key_env("anthropic") == "ANTHROPIC_API_KEY"
    assert provider_api_key_env("gemini") == "GEMINI_API_KEY"
    assert provider_api_key_env("ollama") is None


class TestDocOllamaRuntimeToggle:
    def test_explicit_disable(self, monkeypatch):
        monkeypatch.setenv("DOC_OLLAMA_ENABLED", "0")
        monkeypatch.delenv("SPACE_ID", raising=False)
        assert doc_ollama_runtime_enabled() is False

    def test_explicit_enable_overrides_space_id(self, monkeypatch):
        monkeypatch.setenv("DOC_OLLAMA_ENABLED", "1")
        monkeypatch.setenv("SPACE_ID", "user/demo")
        assert doc_ollama_runtime_enabled() is True

    def test_space_id_disables_when_unset(self, monkeypatch):
        monkeypatch.delenv("DOC_OLLAMA_ENABLED", raising=False)
        monkeypatch.setenv("SPACE_ID", "user/demo")
        assert doc_ollama_runtime_enabled() is False

    def test_load_config_strips_ollama_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DOC_OLLAMA_ENABLED", "false")
        path = _write_config({})
        try:
            cfg = load_config(path)
            assert "ollama" not in cfg.llm.allowed_models_by_provider
            assert cfg.llm.default_provider != "ollama"
            assert cfg.llm.default_provider in cfg.llm.allowed_models_by_provider
        finally:
            os.unlink(path)
