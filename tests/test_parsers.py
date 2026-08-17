from odyssey_monitor.config import Config
from odyssey_monitor.maoyan import extract_showtimes_from_json, extract_showtimes_from_html


def test_json_nested_date_plist():
    cfg = Config()
    payload = {
        "data": {
            "movies": [
                {
                    "nm": "奥德赛",
                    "shows": [
                        {
                            "showDate": "2026-08-18",
                            "plist": [
                                {"tm": "09:45", "th": "IMAX 激光厅", "tp": "英语IMAX2D", "seqNo": "a"},
                                {"tm": "13:10", "th": "3号厅", "tp": "英语2D", "seqNo": "b"},
                            ],
                        }
                    ],
                },
                {
                    "nm": "别的电影",
                    "shows": [{"showDate": "2026-08-18", "plist": [{"tm": "19:00", "th": "IMAX 激光厅", "tp": "IMAX"}]}],
                },
            ]
        }
    }
    items = extract_showtimes_from_json(payload, cfg)
    assert [(x.show_date, x.start_time, x.hall) for x in items] == [
        ("2026-08-18", "09:45", "IMAX 激光厅")
    ]


def test_html_panel_and_tables():
    cfg = Config()
    html = """
    <div class='show-list'>
      <h3 class='movie-name'>奥德赛</h3>
      <div class='show-date'>
        <span class='date-item' data-date='2026-08-18'>8月18</span>
      </div>
      <div class='plist-container'>
        <table class='plist'><tr>
          <td><span class='begin-time'>09:45</span></td>
          <td><span class='lang'>英语IMAX2D</span></td>
          <td><span class='hall'>IMAX 激光厅</span></td>
        </tr></table>
      </div>
    </div>
    """
    items = extract_showtimes_from_html(html, cfg)
    assert len(items) == 1
    assert items[0].show_date == "2026-08-18"
    assert items[0].start_time == "09:45"
