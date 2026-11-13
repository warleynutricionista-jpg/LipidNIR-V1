"""Liga cada implementação existente à bateria do seu contrato."""

import pytest

from lipidence_modular.jobs.in_process import InProcessJobRunner
from lipidence_modular.storage.local import LocalArtifactStorage
from lipidence_modular.tests.contracts.artifact_storage_contract import ArtifactStorageContract
from lipidence_modular.tests.contracts.job_runner_contract import JobRunnerContract


class TestLocalArtifactStorage(ArtifactStorageContract):
    @pytest.fixture()
    def storage(self, tmp_path):
        return LocalArtifactStorage(tmp_path / "store")

    def test_no_temporary_files_left_or_listed(self, storage):
        storage.put_bytes("a", b"1")
        storage.put_bytes("a", b"1")
        assert storage.list_keys() == ["a"]
        assert not list((storage.root / ".tmp").iterdir())


class TestInProcessJobRunner(JobRunnerContract):
    @pytest.fixture()
    def runner(self):
        runner = InProcessJobRunner()
        yield runner
        runner.shutdown()

    def test_submit_after_shutdown_is_an_error(self, runner):
        runner.shutdown()
        with pytest.raises(Exception, match="encerrado"):
            runner.submit("x", lambda: None)
