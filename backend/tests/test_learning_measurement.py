ROOT = {
    "name": "Priya Shah",
    "email": "priya.shah@example.com",
    "password": "correct horse battery staple",
}


def _start_human_session(client) -> None:
    response = client.post("/auth/setup-root", json=ROOT)
    assert response.status_code == 201, response.text
    client.headers.pop("Authorization", None)
    client.headers["Origin"] = "http://localhost:3000"


def test_learning_events_require_a_human_session(client):
    response = client.post(
        "/learning-events",
        json={
            "event_type": "search_miss",
            "query": "pay cycle",
            "path": "/dashboard",
        },
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_learning_insights_aggregate_feedback_and_search_misses(client):
    _start_human_session(client)

    for payload in (
        {
            "event_type": "article_feedback",
            "article_id": "B01",
            "path": "/learn/start-here/what-policyos-does",
            "helpful": True,
            "reason": "clear",
        },
        {
            "event_type": "article_feedback",
            "article_id": "B01",
            "path": "/learn/start-here/what-policyos-does",
            "helpful": False,
            "reason": "hard_to_follow",
        },
        {
            "event_type": "search_miss",
            "query": "  Pay Cycle  ",
            "path": "/dashboard",
        },
        {
            "event_type": "search_miss",
            "query": "pay cycle",
            "path": "/employees",
        },
    ):
        response = client.post("/learning-events", json=payload)
        assert response.status_code == 201, response.text
        assert "user_id" not in response.json()

    response = client.get("/learning-insights")
    assert response.status_code == 200, response.text
    insights = response.json()
    assert insights["total_feedback"] == 2
    assert insights["helpful_percentage"] == 50.0
    assert insights["article_feedback"] == [
        {"article_id": "B01", "helpful_count": 1, "not_helpful_count": 1}
    ]
    assert insights["unsuccessful_searches"][0]["query"] == "pay cycle"
    assert insights["unsuccessful_searches"][0]["count"] == 2

    private_query = client.post(
        "/learning-events",
        json={
            "event_type": "search_miss",
            "query": "Avery@example.com employee 123456",
            "path": "/employees",
        },
    )
    assert private_query.status_code == 201
    assert private_query.json()["query"] == "[email] employee [number]"


def test_learning_event_shape_is_strict(client):
    _start_human_session(client)

    response = client.post(
        "/learning-events",
        json={
            "event_type": "search_miss",
            "query": "missing",
            "path": "/dashboard",
            "helpful": False,
        },
    )
    assert response.status_code == 422

    response = client.post(
        "/learning-events",
        json={
            "event_type": "article_feedback",
            "article_id": "B01",
            "path": "https://example.com/learn",
            "helpful": True,
        },
    )
    assert response.status_code == 422
