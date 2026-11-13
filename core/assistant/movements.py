"""Deterministic drafts only. No provider is called and no financial row is written."""
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from rest_framework import serializers

from core.models import Category, FamilyCategoryAlias, Month


def normalize(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', value)).strip()


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Expected an object.')
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Unknown field.' for key in sorted(unknown)})
        return super().to_internal_value(data)


class DraftInput(StrictSerializer):
    text = serializers.CharField(max_length=4000)
    year = serializers.IntegerField(min_value=1, max_value=9999)
    month = serializers.IntegerField(min_value=1, max_value=12)


class MovementInput(StrictSerializer):
    kind = serializers.ChoiceField(choices=('expense', 'income'))
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    date = serializers.DateField()
    category = serializers.IntegerField(min_value=1)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    alias = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    learn_alias = serializers.BooleanField(required=False, default=False)

    def validate(self, data):
        family = self.context['family']
        if not Category.objects.filter(pk=data['category'], family=family).exists():
            raise serializers.ValidationError({'category': 'Category does not belong to your family.'})
        if Month.objects.filter(family=family, year=data['date'].year, month=data['date'].month, is_closed=True).exists():
            raise serializers.ValidationError({'date': 'This month is closed and cannot be modified.'})
        data['alias'] = normalize(data['alias'])
        if data['learn_alias'] and not data['alias']:
            raise serializers.ValidationError({'alias': 'An explicit alias is required to learn it.'})
        if data['learn_alias'] and FamilyCategoryAlias.objects.filter(family=family, alias=data['alias']).exclude(category_id=data['category']).exists():
            raise serializers.ValidationError({'alias': 'This alias already belongs to a different category.'})
        return data


class ProposalInput(StrictSerializer):
    movements = MovementInput(many=True, min_length=1, max_length=20)

    def validate_movements(self, movements):
        learned = {}
        for row in movements:
            if row['learn_alias']:
                if row['alias'] in learned and learned[row['alias']] != row['category']:
                    raise serializers.ValidationError('One alias cannot refer to different categories.')
                learned[row['alias']] = row['category']
        return movements


def draft_movements(text, year, month, family):
    lines = [line.strip() for line in re.split(r'[;\n]+', text) if line.strip()]
    if not 1 <= len(lines) <= 20:
        raise serializers.ValidationError({'text': 'Write between 1 and 20 movements, one per line.'})
    today = timezone.localdate()
    default_date = today if (today.year, today.month) == (year, month) else date(year, month, 1)
    categories = list(Category.objects.filter(family=family))
    aliases = list(FamilyCategoryAlias.objects.filter(family=family, category__family=family))
    rows = []
    for line in lines:
        errors = []
        description = line[:255]
        normalized = normalize(line)
        income = bool(re.search(r'\b(ingreso|ingrese|cobre|cobro|recibi|nomina|salario)\b', normalized))
        expense = bool(re.search(r'\b(gasto|gaste|pago|pague|compre|compra)\b', normalized))
        kind = 'income' if income and not expense else 'expense' if expense and not income else None
        if kind is None:
            errors.append('Indica si es un gasto o un ingreso.')
        dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', line)
        parsed_date = default_date.isoformat()
        if dates:
            try:
                parsed_date = date.fromisoformat(dates[0]).isoformat()
                if len(dates) > 1:
                    raise ValueError()
            except ValueError:
                errors.append('Revisa la fecha.')
                parsed_date = None
        unsupported_time = re.search(
            r'\b(ayer|anteayer|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo|'
            r'enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|'
            r'semana|mes|ano|pasado|pasada|anterior|proximo|proxima|dia)\b|\bel\s+\d{1,2}\b', normalized,
        ) or re.search(r'\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b', re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', line))
        if unsupported_time:
            parsed_date = None
            errors.append('Introduce la fecha exacta del movimiento.')
        elif re.search(r'\bhoy\b', normalized):
            if dates and dates[0] != today.isoformat():
                parsed_date = None
                errors.append('La fecha indicada no coincide con hoy. Revisa la fecha.')
            else:
                parsed_date = today.isoformat()
                if (today.year, today.month) != (year, month):
                    errors.append('Hoy pertenece a otro período. Revisa la fecha antes de guardar.')
        without_dates = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', '', line)
        amounts = re.findall(r'(?<![\w.,])[-+]?\d+(?:[.,]\d{1,2})?(?![\w.,])', without_dates)
        amount = None
        if len(amounts) == 1:
            try:
                parsed_amount = Decimal(amounts[0].replace(',', '.'))
                if not Decimal('0') < parsed_amount <= Decimal('99999999.99'):
                    raise InvalidOperation()
                amount = str(parsed_amount.quantize(Decimal('.01')))
            except InvalidOperation:
                errors.append('Revisa el importe: debe ser positivo y tener como máximo ocho cifras enteras.')
        else:
            errors.append('Indica un único importe por movimiento.')
        matches = {c.pk for c in categories if f' {normalize(c.name)} ' in f' {normalized} '}
        alias_matches = [a for a in aliases if f' {a.alias} ' in f' {normalized} ']
        matches.update(a.category_id for a in alias_matches)
        category = next(iter(matches)) if len(matches) == 1 else None
        if category is None:
            errors.append('Elige una categoría; no hay una coincidencia única.')
        rows.append({'kind': kind, 'amount': amount, 'date': parsed_date, 'category': category,
                     'description': description, 'alias': '', 'learn_alias': False, 'errors': errors})
    return rows
