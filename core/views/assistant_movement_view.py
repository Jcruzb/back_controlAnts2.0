"""Explicit prepare/confirm boundary for assistant-originated money movements."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.assistant.movements import DraftInput, ProposalInput, draft_movements
from core.models import Family, FamilyCategoryAlias, Month, MovementProposal, Profile
from core.serializers.expense_serializer import ExpenseSerializer
from core.serializers.income_serializer import IncomeSerializer
from core.views.expense_viewset import ExpenseViewSet
from core.views.income_viewset import IncomeViewSet


class AssistantMovementBase(APIView):
    permission_classes = [IsAuthenticated]

    def family(self, request):
        if not settings.ASSISTANT_ENABLED:
            raise NotFound('El asistente está desactivado.')
        return get_object_or_404(Profile, user=request.user).family


def movement_serializer(row, request):
    data = {key: row[key] for key in ('amount', 'date', 'category', 'description')}
    cls = ExpenseSerializer if row['kind'] == 'expense' else IncomeSerializer
    serializer = cls(data=data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    return serializer


class AssistantMovementDraftView(AssistantMovementBase):
    def post(self, request):
        family = self.family(request)
        serializer = DraftInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({'rows': draft_movements(family=family, **serializer.validated_data),
                         'source': 'deterministic', 'requires_confirmation': True})


class AssistantMovementProposalView(AssistantMovementBase):
    def post(self, request):
        family = self.family(request)
        serializer = ProposalInput(data=request.data, context={'family': family})
        serializer.is_valid(raise_exception=True)
        # Store only validated canonical JSON; clients cannot later edit this payload.
        movements = list(serializer.data['movements'])
        for row in movements:
            movement_serializer(row, request)
        proposal = MovementProposal.objects.create(family=family, actor=request.user,
            movements=movements, expires_at=timezone.now() + timedelta(minutes=15))
        return Response({'id': str(proposal.pk), 'expires_at': proposal.expires_at,
                         'movements': proposal.movements, 'requires_confirmation': True}, status=201)


class AssistantMovementConfirmView(AssistantMovementBase):
    @transaction.atomic
    def post(self, request, proposal_id):
        family = self.family(request)
        # A literal boolean is required: strings, additional rows or tenant fields fail.
        if not isinstance(request.data, dict) or set(request.data) != {'confirmed'} or request.data['confirmed'] is not True:
            raise ValidationError({'confirmed': 'Explicit confirmed:true is required.'})
        proposal = get_object_or_404(MovementProposal.objects.select_for_update(),
                                    pk=proposal_id, family=family, actor=request.user)
        if proposal.confirmed_at is not None:
            return Response({'id': str(proposal.pk), 'created': False, 'movements': proposal.result})
        if proposal.expires_at <= timezone.now():
            return Response({'detail': 'La propuesta ha caducado. Revisa una nueva propuesta.'}, status=409)

        # Serialize family alias learning and month creation across concurrent batches.
        Family.objects.select_for_update().get(pk=family.pk)
        serializer = ProposalInput(data={'movements': proposal.movements}, context={'family': family})
        serializer.is_valid(raise_exception=True)
        for row in serializer.validated_data['movements']:
            month, _ = Month.objects.get_or_create(family=family, year=row['date'].year, month=row['date'].month)
            month = Month.objects.select_for_update().get(pk=month.pk)
            if month.is_closed:
                raise ValidationError({'date': 'This month is closed and cannot be modified.'})
        result = []
        for row in proposal.movements:
            serializer = movement_serializer(row, request)
            view = ExpenseViewSet() if row['kind'] == 'expense' else IncomeViewSet()
            view.request = request
            view.perform_create(serializer)
            result.append({'kind': row['kind'], 'id': serializer.instance.pk})
            if row['learn_alias']:
                FamilyCategoryAlias.objects.get_or_create(family=family, alias=row['alias'],
                    defaults={'category_id': row['category'], 'learned_by': request.user})
        proposal.result = result
        proposal.confirmed_at = timezone.now()
        proposal.save(update_fields=['result', 'confirmed_at'])
        return Response({'id': str(proposal.pk), 'created': True, 'movements': result})
