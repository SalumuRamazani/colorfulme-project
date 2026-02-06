from colorfulme.services.openai_client import OpenAIClient


def test_estimate_image_cost_known_model():
    cost = OpenAIClient.estimate_image_cost_usd('gpt-image-1.5', 'medium', '1024x1024')
    assert cost == 0.034


def test_estimate_image_cost_unknown_model_returns_none():
    cost = OpenAIClient.estimate_image_cost_usd('unknown-model', 'medium', '1024x1024')
    assert cost is None
