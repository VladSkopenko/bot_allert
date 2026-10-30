from bot_allert.state import load_folder, save_folder


def test_missing_file_means_no_folder(tmp_path):
    assert load_folder(tmp_path / "state.json") is None


def test_saved_folder_survives_reload(tmp_path):
    path = tmp_path / "nested" / "state.json"

    save_folder(path, "Тревоги")

    assert load_folder(path) == "Тревоги"


def test_corrupted_file_means_no_folder(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json")

    assert load_folder(path) is None


def test_non_string_folder_means_no_folder(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"folder": 5}')

    assert load_folder(path) is None
