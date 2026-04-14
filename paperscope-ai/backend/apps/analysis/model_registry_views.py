from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .model_registry_service import (
    list_models,
    get_active_model,
    set_active_model,
    refresh_registry_from_disk,
    predict_with_active_model,
)


def is_admin_user(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "role", None) == "ADMIN")


class AdminModelListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        return Response({"models": list_models()}, status=status.HTTP_200_OK)


class AdminModelActivateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        model_id = request.data.get("model_id")
        if not model_id:
            return Response({"detail": "model_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            set_active_model(model_id)
            return Response(
                {
                    "message": "Model activated successfully.",
                    "active_model": get_active_model(),
                },
                status=status.HTTP_200_OK,
            )
        except FileNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminModelRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not is_admin_user(request.user):
            return Response({"detail": "Admin only."}, status=status.HTTP_403_FORBIDDEN)

        models = refresh_registry_from_disk()
        return Response(
            {
                "message": "Model registry refreshed.",
                "models": models,
            },
            status=status.HTTP_200_OK,
        )


class ActiveModelDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        active = get_active_model()
        if not active:
            return Response({"detail": "No active model configured."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"active_model": active}, status=status.HTTP_200_OK)


class ActiveModelPredictView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            result = predict_with_active_model(request.data)
            return Response(result, status=status.HTTP_200_OK)
        except FileNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)