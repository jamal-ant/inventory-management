"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingRecommendations:
    """Test suite for restocking recommendation endpoint."""

    def test_zero_budget_returns_empty(self, client):
        """Test that a zero budget returns no recommendations."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200
        assert response.json() == []

    def test_large_budget_returns_all_items(self, client):
        """Test that a very large budget returns all nine forecast items."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 9

    def test_increasing_trend_prioritized_first(self, client):
        """Test that increasing-trend items appear before stable and decreasing."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        trend_order = {"increasing": 0, "stable": 1, "decreasing": 2}
        priorities = [trend_order[item["trend"]] for item in data]
        assert priorities == sorted(priorities)
        assert data[0]["trend"] == "increasing"

    def test_recommendations_fit_within_budget(self, client):
        """Test that total of all recommended line items never exceeds budget."""
        budget = 50000
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        assert response.status_code == 200

        data = response.json()
        total = sum(item["line_total"] for item in data)
        assert total <= budget

    def test_recommendation_structure(self, client):
        """Test that each recommendation has all required fields."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()
        assert len(data) > 0

        required_fields = [
            "item_sku", "item_name", "trend", "recommended_quantity",
            "unit_cost", "line_total", "lead_time_days",
        ]
        for item in data:
            for field in required_fields:
                assert field in item, f"Missing field: {field}"

    def test_recommendation_field_types(self, client):
        """Test that recommendation numeric fields have correct types."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        for item in data:
            assert isinstance(item["recommended_quantity"], int)
            assert isinstance(item["unit_cost"], (int, float))
            assert isinstance(item["line_total"], (int, float))
            assert isinstance(item["lead_time_days"], int)
            assert item["recommended_quantity"] > 0
            assert item["unit_cost"] > 0
            assert item["lead_time_days"] > 0

    def test_line_total_matches_quantity_times_cost(self, client):
        """Test that line_total equals recommended_quantity * unit_cost."""
        response = client.get("/api/restocking/recommendations?budget=1000000")
        data = response.json()

        for item in data:
            expected = item["recommended_quantity"] * item["unit_cost"]
            assert abs(item["line_total"] - expected) < 0.01

    def test_default_budget_is_zero(self, client):
        """Test that omitting the budget param defaults to zero (empty result)."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200
        assert response.json() == []


class TestRestockingOrders:
    """Test suite for restocking order creation and listing."""

    def test_create_order_returns_201(self, client):
        """Test that creating a valid restocking order returns 201."""
        payload = {
            "items": [
                {
                    "item_sku": "WDG-001",
                    "item_name": "Industrial Widget Type A",
                    "quantity": 100,
                    "unit_cost": 18.5,
                    "line_total": 1850.0,
                }
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["order_number"].startswith("RST-")
        assert data["total_cost"] == 1850.0
        assert data["lead_time_days"] > 0
        assert data["status"] == "Submitted"

    def test_create_order_structure(self, client):
        """Test that a created order has all required fields."""
        payload = {
            "items": [
                {
                    "item_sku": "GSK-203",
                    "item_name": "High-Temperature Gasket",
                    "quantity": 50,
                    "unit_cost": 12.75,
                    "line_total": 637.5,
                }
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        data = response.json()

        required_fields = [
            "id", "order_number", "items", "total_cost",
            "lead_time_days", "created_date", "expected_delivery", "status",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

        assert isinstance(data["items"], list)
        assert len(data["items"]) == 1
        assert data["items"][0]["item_sku"] == "GSK-203"

    def test_empty_order_returns_400(self, client):
        """Test that submitting an order with no items returns 400."""
        response = client.post("/api/restocking/orders", json={"items": []})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data
        assert "at least one item" in data["detail"].lower()

    def test_order_lead_time_is_max_of_items(self, client):
        """Test that order lead time equals the maximum lead time across items."""
        # MTR-304 has lead_time_days=21 (highest in dataset)
        payload = {
            "items": [
                {
                    "item_sku": "WDG-001",
                    "item_name": "Industrial Widget Type A",
                    "quantity": 10,
                    "unit_cost": 18.5,
                    "line_total": 185.0,
                },
                {
                    "item_sku": "MTR-304",
                    "item_name": "Electric Motor 5HP",
                    "quantity": 5,
                    "unit_cost": 145.0,
                    "line_total": 725.0,
                },
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["lead_time_days"] == 21

    def test_order_total_is_sum_of_line_totals(self, client):
        """Test that total_cost equals the sum of all line totals."""
        payload = {
            "items": [
                {
                    "item_sku": "FLT-405",
                    "item_name": "Oil Filter Cartridge",
                    "quantity": 100,
                    "unit_cost": 8.25,
                    "line_total": 825.0,
                },
                {
                    "item_sku": "SNR-420",
                    "item_name": "Temperature Sensor Module",
                    "quantity": 50,
                    "unit_cost": 24.0,
                    "line_total": 1200.0,
                },
            ]
        }
        response = client.post("/api/restocking/orders", json=payload)
        data = response.json()
        assert abs(data["total_cost"] - 2025.0) < 0.01

    def test_created_order_appears_in_list(self, client):
        """Test that a created order is returned by the list endpoint."""
        payload = {
            "items": [
                {
                    "item_sku": "VLV-506",
                    "item_name": "Pressure Relief Valve",
                    "quantity": 25,
                    "unit_cost": 68.0,
                    "line_total": 1700.0,
                }
            ]
        }
        create_response = client.post("/api/restocking/orders", json=payload)
        assert create_response.status_code == 201
        order_number = create_response.json()["order_number"]

        list_response = client.get("/api/restocking/orders")
        assert list_response.status_code == 200

        order_numbers = [o["order_number"] for o in list_response.json()]
        assert order_number in order_numbers

    def test_list_orders_returns_list(self, client):
        """Test that the list endpoint returns a list."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
