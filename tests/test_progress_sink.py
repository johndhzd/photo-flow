from photo_flow.progress import ProgressBar, progress_sink


def test_progress_sink_receives_updates_and_writes_nothing_to_stderr(capsys):
    events: list[tuple[int, int, str]] = []

    with progress_sink(lambda current, total, desc: events.append((current, total, desc))):
        with ProgressBar(3, desc="Work") as bar:
            bar.advance("a")
            bar.advance("b")

    assert events == [(1, 3, "Work"), (2, 3, "Work")]
    assert capsys.readouterr().err == ""


def test_progress_sink_is_restored_after_context(capsys):
    seen: list[tuple[int, int, str]] = []
    with progress_sink(lambda current, total, desc: seen.append((current, total, desc))):
        pass

    # Outside the context there is no sink; the bar falls back to its stderr
    # behaviour, which is a no-op under pytest (stderr is not a TTY).
    with ProgressBar(2, desc="After") as bar:
        bar.advance()

    assert seen == []
    assert capsys.readouterr().err == ""
