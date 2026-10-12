from rest_framework import serializers


class AISummarySerializer(serializers.Serializer):
    currency=serializers.CharField()
    start_date=serializers.DateTimeField()
    end_date=serializers.DateTimeField()
    period=serializers.CharField()
    income=serializers.DecimalField(max_digits=20,decimal_places=8)
    expense=serializers.DecimalField(max_digits=20,decimal_places=8)
    net=serializers.DecimalField(max_digits=20,decimal_places=8)
    expenses_by_category=serializers.DictField(child=serializers.DecimalField(
        max_digits=20,
        decimal_places=8
    ))
    summary=serializers.CharField()
    insights=serializers.ListField(child=serializers.CharField())
    recommendations=serializers.ListField(child=serializers.CharField())
