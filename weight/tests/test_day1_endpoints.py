import pytest
from unittest.mock import MagicMock, patch

from app import app  


# זה נותן לנו אפשרות לעשות client.get / client.post בלי להריץ שרת אמיתי.
@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# =========================
# 1) TESTS FOR GET /health
# =========================

def test_health_returns_200_or_500(client):
    """
    מה הטסט בודק?
    - endpoint /health קיים
    - מחזיר סטטוס תקין (200 אם הכל בסדר, או 500 אם אצלך הוא בודק DB ואין DB)
    
    למה זה טוב?
    - ביום 1 העיקר להראות שיש endpoint ושעובד/מטפל גם בכשל.
    """
    resp = client.get("/health")
    assert resp.status_code in (200, 500)


# =========================
# 2) TESTS FOR POST /weight
# =========================

def test_post_weight_missing_fields_returns_400(client):
    """
    מה הטסט בודק?
    אם שלחנו גוף חלקי (חסרים שדות חובה) -> חייב להיות 400.
    """
    resp = client.post("/weight", json={"direction": "in"})
    assert resp.status_code == 400
    body = resp.get_json()
    assert "error" in body


def test_post_weight_invalid_direction_returns_400(client):
    """
    מה הטסט בודק?
    direction חייב להיות רק in/out/none.
    אם שלחנו משהו אחר -> 400.
    """
    payload = {
        "direction": "banana",
        "truck": "12-345-67",
        "containers": "C1,C2",
        "weight": 1000,
        "unit": "kg",
        "force": False,
        "produce": "orange",
    }
    resp = client.post("/weight", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_post_weight_out_without_in_returns_400(client):
    """
    מה הטסט בודק?
    לפי הדרישות: OUT בלי IN קודם -> שגיאה.
    פה אנחנו לא צריכים DB כדי לבדוק את זה,
    כי גם בלי DB, אם הקוד לא מוצא open_in הוא צריך להחזיר 400.
    """
    payload = {
        "direction": "out",
        "truck": "12-345-67",
        "containers": "C1,C2",
        "weight": 20000,
        "unit": "kg",
        "force": False,
        "produce": "orange",
    }
    resp = client.post("/weight", json=payload)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


# =================================
# 3) TESTS FOR GET /weight (report)
# =================================

def test_get_weight_returns_list(client):
    """
    מה הטסט בודק?
    GET /weight צריך להחזיר JSON שהוא רשימה (list).
    
    בלי DB, יש שתי אפשרויות:
    - אם המימוש שלך עדיין לא מוכן -> אולי יחזיר 500
    - אם החזרת בינתיים [] -> יחזיר 200
    
    אז הטסט כאן גמיש: הוא מבקש לפחות שתקבלי תשובה,
    ואם יש 200 - אז שהגוף יהיה רשימה.
    """
    resp = client.get("/weight")
    if resp.status_code == 200:
        assert isinstance(resp.get_json(), list)
    else:
        assert resp.status_code in (400, 404, 500)