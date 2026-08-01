from app.domain.render.phrase_align import snap_trim_to_phrase

# source_bpm=120 → one 4/4 bar = 4*60/120 = 2.0 s, so whole-bar shifts are
# exact multiples of 2000 ms. Makes the whole-bar arithmetic readable.
BPM = 120.0


def test_whole_bar_shift_applied():
    # trim at 10.0s, boundary at 12.0s → +1 bar (2000ms), in-window
    assert snap_trim_to_phrase(10.0, [12000], BPM) == 12.0


def test_two_bar_shift_applied():
    assert snap_trim_to_phrase(8.0, [12000], BPM) == 12.0


def test_four_bar_shift_at_window_edge():
    # exactly window_bars=4 → accepted
    assert snap_trim_to_phrase(4.0, [12000], BPM) == 12.0


def test_non_whole_bar_shift_rejected():
    # delta 3000ms = 1.5 bars → not within 0.05 of an integer → unchanged
    assert snap_trim_to_phrase(9.0, [12000], BPM) == 9.0


def test_out_of_window_rejected():
    # delta 10000ms = 5 bars > window_bars=4 → unchanged
    assert snap_trim_to_phrase(2.0, [12000], BPM) == 2.0


def test_no_boundaries_noop():
    assert snap_trim_to_phrase(10.0, [], BPM) == 10.0


def test_none_boundaries_noop():
    assert snap_trim_to_phrase(10.0, None, BPM) == 10.0


def test_near_whole_bar_within_tolerance_applied():
    # delta 1900ms = 0.95 bars → within 0.05 of 1 bar → accepted
    assert snap_trim_to_phrase(10.1, [12000], BPM) == 12.0


def test_nearest_boundary_wins():
    # boundaries at 11.5s and 16.0s; trim 12.4s → nearest 11.5s (−0.9s,
    # not whole-bar) → unchanged
    assert snap_trim_to_phrase(12.4, [11500, 16000], BPM) == 12.4
