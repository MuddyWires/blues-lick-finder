from lick_finder.youtube_data import load_topics, topic_url


def test_a_plain_topic_is_a_youtube_search():
    assert topic_url("BB King box licks", 10) == "ytsearch10:BB King box licks"


def test_a_channel_handle_is_that_channels_videos_tab():
    assert topic_url("channel:@guitarcompass", 10) == "https://www.youtube.com/@guitarcompass/videos"


def test_a_channel_id_is_that_channels_videos_tab():
    assert topic_url("channel:UCkTfxhJAJjCBITdmu2Cx1xw", 10) == (
        "https://www.youtube.com/channel/UCkTfxhJAJjCBITdmu2Cx1xw/videos"
    )


def test_whitespace_around_a_channel_ref_is_ignored():
    assert topic_url("channel: @guitarcompass ", 10) == "https://www.youtube.com/@guitarcompass/videos"


def test_load_topics_keeps_channel_lines_and_skips_comments_and_blanks(tmp_path):
    topics = tmp_path / "topics.txt"
    topics.write_text("# a comment\n\nBB King box licks\n# Guitar Compass\nchannel:@guitarcompass\n")

    assert load_topics(topics) == ["BB King box licks", "channel:@guitarcompass"]
