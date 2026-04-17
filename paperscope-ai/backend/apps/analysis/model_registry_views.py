from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .model_registry_service import (
    get_active_model,
    list_models,
    predict_with_active_model,
    refresh_registry_from_disk,
    set_active_model,
)


def is_admin_user(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", None) == "ADMIN")


def _pick_first(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _as_float(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_test_accuracy(entry):
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}

    candidates = [
        entry.get("test_accuracy"),
        entry.get("test_acc"),
        metadata.get("test_accuracy"),
        metadata.get("test_acc"),
        metadata.get("accuracy"),
    ]

    metrics = metadata.get("metrics")
    if isinstance(metrics, dict):
        candidates.extend(
            [
                metrics.get("testAccuracy"),
                metrics.get("test_accuracy"),
                metrics.get("test_acc"),
                metrics.get("accuracy"),
            ]
        )

    evaluation = metadata.get("evaluation")
    if isinstance(evaluation, dict):
        candidates.extend(
            [
                evaluation.get("testAccuracy"),
                evaluation.get("test_accuracy"),
                evaluation.get("test_acc"),
                evaluation.get("accuracy"),
            ]
        )

    for candidate in candidates:
        numeric = _as_float(candidate)
        if numeric is not None:
            return numeric
    return None


def _build_model_type(entry):
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}

    explicit = _pick_first(
        entry.get("modelType"),
        entry.get("model_type"),
        metadata.get("model_type"),
    )
    if explicit:
        return explicit

    parts = [
        metadata.get("vectorizer_type"),
        metadata.get("classifier_type"),
    ]
    parts = [part for part in parts if part]
    if parts:
        return " + ".join(parts)

    return _pick_first(metadata.get("model_name"), entry.get("domain"), "")


def _build_status(entry):
    if entry.get("score_calibrator_path"):
        return "Calibrated"
    return "Ready"


def _serialize_model_entry(entry):
    payload = dict(entry or {})
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}

    model_key = _pick_first(
        payload.get("model_key"),
        payload.get("model_id"),
        payload.get("id"),
        payload.get("pk"),
    )

    display_name = _pick_first(
        payload.get("display_name"),
        payload.get("name"),
        payload.get("model_name"),
        metadata.get("display_name"),
        metadata.get("model_name"),
        model_key,
        "Unnamed model",
    )

    created_at = _pick_first(
        payload.get("created_at"),
        payload.get("createdAt"),
        payload.get("trained_at"),
        metadata.get("created_at"),
        metadata.get("trained_at"),
        payload.get("run_id"),
        metadata.get("run_id"),
        "Unknown",
    )

    active = bool(
        payload.get("active")
        or payload.get("is_active")
        or payload.get("active_flag")
    )

    test_accuracy = _extract_test_accuracy(payload)
    model_type = _build_model_type(payload)
    status_text = _build_status(payload)

    payload.update(
        {
            "id": model_key,
            "model_id": model_key,
            "pk": model_key,
            "name": display_name,
            "display_name": display_name,
            "active": active,
            "is_active": active,
            "createdAt": created_at,
            "created_at": created_at,
            "modelType": model_type,
            "model_type": model_type,
            "status": status_text,
            "metrics": {
                "testAccuracy": test_accuracy,
                "test_accuracy": test_accuracy,
            },
        }
    )
    return payload


def _serialize_model_list(items):
    serialized = [_serialize_model_entry(item) for item in items]
    serialized.sort(key=lambda item: (not item.get("active", False), str(item.get("name", "")).lower()))
    return serialized


class AdminModelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        return Response({"models": _serialize_model_list(list_models())}, status=status.HTTP_200_OK)


class AdminModelActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        model_key = (
            request.data.get("model_key")
            or request.data.get("model_id")
            or request.data.get("id")
        )
        if not model_key:
            return Response(
                {"detail": "model_key is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            registry = set_active_model(str(model_key))
            active_model = get_active_model()
            return Response(
                {
                    "message": "Active model updated successfully.",
                    "active_model": registry.get("active_model"),
                    "model": _serialize_model_entry(active_model) if active_model else None,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminModelRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        registry = refresh_registry_from_disk()
        models = _serialize_model_list(list_models())

        return Response(
            {
                "message": "Model registry refreshed successfully.",
                "active_model": registry.get("active_model"),
                "count": len(models),
                "models": models,
            },
            status=status.HTTP_200_OK,
        )


class ActiveModelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active_model = get_active_model()
        if not active_model:
            return Response({"detail": "No active model configured."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"model": _serialize_model_entry(active_model)}, status=status.HTTP_200_OK)


class ActiveModelPredictView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data or {}
        try:
            prediction = predict_with_active_model(data)
            return Response(prediction, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)