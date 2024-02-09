# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import signal
import subprocess
import tempfile
from pathlib import Path

import pytest
from utils import (
    check_magika_cli_output_matches_expected_by_ext,
    get_magika_cli_output_from_stdout_stderr,
)
from utils_magika_python_client import (
    run_magika_python_cli,
)

from magika.content_types import ContentType, ContentTypesManager
from magika.prediction_mode import PredictionMode
from tests import utils


@pytest.mark.smoketest
def test_magika_python_cli_with_one_test_file():
    test_file_path = utils.get_basic_test_files_paths()[0]

    stdout, stderr = run_magika_python_cli([test_file_path])
    check_magika_cli_output_matches_expected_by_ext([test_file_path], stdout, stderr)

    stdout, stderr = run_magika_python_cli(
        [test_file_path], extra_cli_options=["--json"]
    )
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, json_output=True
    )

    stdout, stderr = run_magika_python_cli(
        [test_file_path], extra_cli_options=["--jsonl"]
    )
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, jsonl_output=True
    )

    stdout, stderr = run_magika_python_cli([test_file_path], extra_cli_options=["-p"])
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, output_probability=True
    )

    stdout, stderr = run_magika_python_cli(
        [test_file_path], extra_cli_options=["--mime-type"]
    )
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, mime_output=True
    )

    stdout, stderr = run_magika_python_cli(
        [test_file_path], extra_cli_options=["--label"]
    )
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, label_output=True
    )

    stdout, stderr = run_magika_python_cli(
        [test_file_path], extra_cli_options=["--compatibility-mode"]
    )
    check_magika_cli_output_matches_expected_by_ext(
        [test_file_path], stdout, stderr, compatibility_mode=True
    )


def test_magika_python_cli_with_very_small_test_files():
    """Magika does not use the DL model for very small files. This test covers
    these scenarios.
    """

    with tempfile.TemporaryDirectory() as td:
        text_test_path = Path(td) / "small.txt"
        text_test_path.write_text("small test")
        stdout, stderr = run_magika_python_cli([text_test_path], label_output=True)
        assert (
            get_magika_cli_output_from_stdout_stderr(stdout, stderr)[0][1]
            == ContentType.GENERIC_TEXT
        )

        binary_test_path = Path(td) / "small.dat"
        binary_test_path.write_bytes(b"\x80\xff")
        stdout, stderr = run_magika_python_cli([binary_test_path], label_output=True)
        assert (
            get_magika_cli_output_from_stdout_stderr(stdout, stderr)[0][1]
            == ContentType.UNKNOWN
        )


def test_magika_cli_with_small_test_files():
    """Magika needs to pad files that are small. This test covers scenarios
    where padding is relevant.
    """

    with tempfile.TemporaryDirectory() as td:
        text_test_path = Path(td) / "small.txt"
        # small, but bigger than the threshold to use the DL model
        text_test_path.write_text("A" * 32)
        _ = run_magika_python_cli([text_test_path], label_output=True)
        # we do not care about the prediction


def test_magika_cli_with_empty_file():
    with tempfile.TemporaryDirectory() as td:
        empty_test_path = Path(td) / "empty.dat"
        empty_test_path.touch()
        stdout, stderr = run_magika_python_cli([empty_test_path], label_output=True)
        assert (
            get_magika_cli_output_from_stdout_stderr(stdout, stderr)[0][1]
            == ContentType.EMPTY
        )


def test_magika_cli_with_directories():
    with tempfile.TemporaryDirectory() as td:
        test_files_num = 3
        for idx in range(test_files_num):
            p = Path(td) / f"test-{idx}.txt"
            p.write_text("test")

        # run without recursive mode
        stdout, stderr = run_magika_python_cli([Path(td)], label_output=True)
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 1
        assert predicted_cts[0][1] == "directory"

        # run with recursive mode
        stdout, stderr = run_magika_python_cli(
            [Path(td)], label_output=True, extra_cli_options=["--recursive"]
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == test_files_num
        for _, ct in predicted_cts:
            assert ct == ContentType.GENERIC_TEXT


def test_magika_cli_with_symlinks():
    with tempfile.TemporaryDirectory() as td:
        test_path = Path(td) / "test.txt"
        test_path.write_text("test")

        symlink_path = Path(td) / "symlink-test.txt"
        symlink_path.symlink_to(test_path)

        # run without --no-dereference mode; symlinks are dereferenced
        stdout, stderr = run_magika_python_cli([symlink_path], label_output=True)
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 1
        assert predicted_cts[0][1] == ContentType.GENERIC_TEXT

        # run with --no-dereference, to avoid dereferencing symlinks
        stdout, stderr = run_magika_python_cli(
            [symlink_path], label_output=True, extra_cli_options=["--no-dereference"]
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 1
        assert predicted_cts[0][1] == "symlink"

        # run with --no-dereference, to avoid dereferencing symlinks
        stdout, stderr = run_magika_python_cli(
            [symlink_path], extra_cli_options=["--no-dereference"]
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 1
        assert isinstance(predicted_cts[0][0], Path)
        assert isinstance(predicted_cts[0][1], str)
        assert predicted_cts[0][1].startswith("Symbolic link")
        assert predicted_cts[0][1].find(str(test_path)) >= 0


def test_magika_cli_with_files_with_permission_errors():
    with tempfile.TemporaryDirectory() as td:
        unreadable_test_path = Path(td) / "test1.txt"
        unreadable_test_path.write_text("test")

        # make it unreadable
        unreadable_test_path.chmod(0o000)

        stdout, stderr = run_magika_python_cli(
            [unreadable_test_path], label_output=True
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 1
        assert predicted_cts[0][1] == ContentType.PERMISSION_ERROR

        # add another, readable file, and check that it is scanned properly
        readable_test_path = Path(td) / "test2.txt"
        readable_test_path.write_text("test")
        stdout, stderr = run_magika_python_cli(
            [unreadable_test_path, readable_test_path], label_output=True
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 2
        assert predicted_cts[0][1] == ContentType.PERMISSION_ERROR
        assert predicted_cts[1][1] == ContentType.GENERIC_TEXT

        # try the same, but passing the directory as input
        stdout, stderr = run_magika_python_cli(
            [Path(td)], label_output=True, extra_cli_options=["--recursive"]
        )
        predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
        assert len(predicted_cts) == 2
        assert predicted_cts[0][1] == ContentType.PERMISSION_ERROR
        assert predicted_cts[1][1] == ContentType.GENERIC_TEXT


def test_magika_cli_with_basic_test_files():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, 5, 10, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n])
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )


def test_magika_cli_with_basic_test_files_and_json_output():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n], json_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, json_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--json"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, json_output=True
        )


def test_magika_cli_with_basic_test_files_and_jsonl_output():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n], jsonl_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, jsonl_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--jsonl"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, jsonl_output=True
        )


def test_magika_cli_with_basic_test_files_and_probability():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], output_probability=True
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, output_probability=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["-p"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, output_probability=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--output-probability"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, output_probability=True
        )


def test_magika_cli_with_basic_test_files_and_mime_output():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n], mime_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, mime_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["-i"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, mime_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--mime-type"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, mime_output=True
        )


def test_magika_cli_with_basic_test_files_and_label_output():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n], label_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, label_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["-l"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, label_output=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--label"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, label_output=True
        )


def test_magika_cli_with_basic_test_files_and_compatibility_mode():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], compatibility_mode=True
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, compatibility_mode=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["-c"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, compatibility_mode=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--compatibility-mode"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, compatibility_mode=True
        )


def test_magika_cli_with_basic_test_files_and_different_prediction_modes():
    # Here we test only the CLI aspect; we test the different behaviors with
    # different prediction modes when we test the Magika module.
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n])
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n],
            extra_cli_options=["--prediction-mode", PredictionMode.MEDIUM_CONFIDENCE],
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n],
            extra_cli_options=["--prediction-mode", PredictionMode.BEST_GUESS],
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n],
            extra_cli_options=["--prediction-mode", PredictionMode.HIGH_CONFIDENCE],
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )

        # Test with invalid prediction mode
        with pytest.raises(subprocess.CalledProcessError):
            _ = run_magika_python_cli(
                test_files_paths[:n],
                extra_cli_options=["--prediction-mode", "non-existing-mode"],
            )


def test_magika_cli_with_python_and_not_python_files():
    with tempfile.TemporaryDirectory() as td:
        # the test needs to be longer than "too small for DL model"
        python_test_path = Path(td) / "real.py"
        python_test_path.write_text("import flask\nimport requests")
        not_python_test_path = Path(td) / "not-real.py"
        not_python_test_path.write_text("xmport asd\nxmport requests")

        # check that a python file is detected as such
        stdout, stderr = run_magika_python_cli(
            [python_test_path], extra_cli_options=["--label"]
        )
        predicted_ct = get_magika_cli_output_from_stdout_stderr(stdout, stderr)[0][1]
        assert predicted_ct == "python"

        # check that a file that is very far from being a python file is
        # detected as text
        stdout, stderr = run_magika_python_cli(
            [not_python_test_path], extra_cli_options=["--label"]
        )
        predicted_ct = get_magika_cli_output_from_stdout_stderr(stdout, stderr)[0][1]
        assert predicted_ct == "txt"


def test_magika_cli_with_basic_test_files_and_custom_batch_sizes():
    test_files_paths = utils.get_basic_test_files_paths()

    for batch_size in [1, 2, 3, 16]:
        for n in [1, 2, 5, len(test_files_paths)]:
            stdout, stderr = run_magika_python_cli(
                test_files_paths[:n], batch_size=batch_size
            )
            check_magika_cli_output_matches_expected_by_ext(
                test_files_paths[:n], stdout, stderr
            )

            stdout, stderr = run_magika_python_cli(
                test_files_paths[:n],
                extra_cli_options=["--batch-size", str(batch_size)],
            )
            check_magika_cli_output_matches_expected_by_ext(
                test_files_paths[:n], stdout, stderr
            )


def test_magika_cli_with_multiple_copies_of_the_same_file():
    max_repetitions_num = 10
    test_file_path = utils.get_one_basic_test_file_path()
    test_files_paths = [test_file_path] * max_repetitions_num

    for n in [2, max_repetitions_num]:
        stdout, stderr = run_magika_python_cli(test_files_paths[:n])
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr
        )

        stdout, stderr = run_magika_python_cli(test_files_paths[:n], json_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, json_output=True
        )

        stdout, stderr = run_magika_python_cli(test_files_paths[:n], jsonl_output=True)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, jsonl_output=True
        )


def test_magika_cli_with_many_files():
    test_file_path = utils.get_one_basic_test_file_path()

    for n in [100, 1000]:
        test_files_paths = [test_file_path] * n
        stdout, stderr = run_magika_python_cli(test_files_paths)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths, stdout, stderr
        )


@pytest.mark.slow
def test_magika_cli_with_really_many_files():
    test_file_path = utils.get_one_basic_test_file_path()

    for n in [10000]:
        test_files_paths = [test_file_path] * n
        stdout, stderr = run_magika_python_cli(test_files_paths)
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths, stdout, stderr
        )


@pytest.mark.slow
def test_magika_cli_with_big_file():
    def signal_handler(signum, frame):
        raise Exception("Timeout")

    signal.signal(signal.SIGALRM, signal_handler)

    # It should take much less than this, but pytest weird scheduling sometimes
    # creates unexpected slow downs.
    timeout = 2

    for sample_size in [1000, 10000, 1_000_000, 1_000_000_000, 10_000_000_000]:
        with tempfile.TemporaryDirectory() as td:
            sample_path = Path(td) / "sample.dat"
            utils.write_random_file_with_size(sample_path, sample_size)
            print(f"Starting running Magika with a timeout of {timeout}")
            signal.alarm(timeout)
            _ = run_magika_python_cli([sample_path])
            signal.alarm(0)
            print("Done running Magika")


def test_magika_cli_with_bad_input():
    test_file_path = utils.get_one_basic_test_file_path()

    # Test without any argument or option
    with pytest.raises(subprocess.CalledProcessError):
        run_magika_python_cli([])

    # Test with file that does not exist
    stdout, stderr = run_magika_python_cli(
        [Path("/this/does/not/exist")], label_output=True
    )
    predicted_cts = get_magika_cli_output_from_stdout_stderr(stdout, stderr)
    assert len(predicted_cts) == 1
    assert predicted_cts[0][1] == ContentType.FILE_DOES_NOT_EXIST

    # Test with incompatible list of options
    with pytest.raises(subprocess.CalledProcessError):
        run_magika_python_cli([test_file_path], json_output=True, jsonl_output=True)

    # Test with an option does not exist
    with pytest.raises(subprocess.CalledProcessError):
        run_magika_python_cli(
            [test_file_path], extra_cli_options=["--non-existing-option"]
        )


def test_magika_cli_with_reading_from_stdin():
    ctm = ContentTypesManager()
    test_file_path = utils.get_one_basic_test_file_path()

    cmd = f"cat {str(test_file_path)} | magika - --jsonl"
    p = subprocess.run(cmd, capture_output=True, text=True, check=True, shell=True)
    stdout, stderr = p.stdout, p.stderr

    entries = get_magika_cli_output_from_stdout_stderr(
        stdout, stderr, jsonl_output=True
    )
    sample_path, entry = entries[0]
    assert isinstance(sample_path, Path)
    assert isinstance(entry, dict)

    file_ext = test_file_path.suffix.lstrip(".")
    true_cts = ctm.get_cts_by_ext(file_ext)
    true_cts_names = [ct.name for ct in true_cts]

    assert str(sample_path) == "-"
    assert str(entry["path"]) == "-"
    assert entry["output"]["ct_label"] in true_cts_names


def test_magika_cli_with_colors():
    test_file_path = utils.get_one_basic_test_file_path()

    # check that it does not crash when using colors and that we are actually
    # using colors
    stdout, stderr = run_magika_python_cli([test_file_path], with_colors=True)
    assert stdout.find("\033") >= 0 or stderr.find("\033") >= 0
    stdout, stderr = run_magika_python_cli(
        [test_file_path], with_colors=True, mime_output=True
    )
    assert stdout.find("\033") >= 0 or stderr.find("\033") >= 0
    stdout, stderr = run_magika_python_cli(
        [test_file_path], with_colors=True, verbose=True, debug=True
    )
    assert stdout.find("\033") >= 0 or stderr.find("\033") >= 0


def test_magika_cli_with_no_colors():
    test_file_path = utils.get_one_basic_test_file_path()

    # check that we are not using colors when --no-colors is passed
    stdout, stderr = run_magika_python_cli([test_file_path], with_colors=False)
    assert stdout.find("\033") == -1 and stderr.find("\033") == -1
    stdout, stderr = run_magika_python_cli(
        [test_file_path], with_colors=False, mime_output=True
    )
    assert stdout.find("\033") == -1 and stderr.find("\033") == -1
    stdout, stderr = run_magika_python_cli(
        [test_file_path], with_colors=False, verbose=True, debug=True
    )
    assert stdout.find("\033") == -1 and stderr.find("\033") == -1


def test_magika_cli_generate_report():
    test_files_paths = utils.get_basic_test_files_paths()

    for n in [1, 2, len(test_files_paths)]:
        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], generate_report=True
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, generate_report=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--generate-report"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, generate_report=True
        )

        stdout, stderr = run_magika_python_cli(
            test_files_paths[:n], extra_cli_options=["--mime-type", "--generate-report"]
        )
        check_magika_cli_output_matches_expected_by_ext(
            test_files_paths[:n], stdout, stderr, mime_output=True, generate_report=True
        )


def test_magika_cli_output_version():
    stdout, stderr = run_magika_python_cli([], extra_cli_options=["--version"])

    lines = utils.get_lines_from_stream(stdout)
    assert len(lines) == 2
    assert lines[0].startswith("Magika version")
    assert lines[1].startswith("Default model name")

    assert stderr == ""


def test_magika_cli_list_content_types():
    test_file_path = utils.get_one_basic_test_file_path()

    stdout, stderr = run_magika_python_cli([], list_output_content_types=True)

    lines = utils.get_lines_from_stream(stdout)
    header = lines[0]
    assert header.find("Content Type Label") >= 0
    assert header.find("MIME Type") >= 0
    assert header.find("Description") >= 0
    assert stderr == ""

    with pytest.raises(subprocess.CalledProcessError):
        run_magika_python_cli([test_file_path], list_output_content_types=True)
