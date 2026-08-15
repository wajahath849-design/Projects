from src.question_analyzer import QuestionAnalyzer


def test_domains_dates_and_facility_are_detected():
    result = QuestionAnalyzer({"energy", "network"}).analyze("Frankfurt PUE in 2020")
    assert result.relevant
    assert result.facilities == ["Frankfurt Central"]
    assert result.years == [2020]


def test_ambiguous_and_unsafe_questions():
    analyzer = QuestionAnalyzer({"energy", "network", "reliability", "server_performance"})
    assert analyzer.analyze("Which facility performs best?").ambiguous
    assert analyzer.analyze("Drop the facilities table").unsafe


def test_missing_module_is_graceful():
    result = QuestionAnalyzer({"energy"}).analyze("Show network latency")
    assert not result.relevant
    assert "unavailable" in result.clarification.lower()
