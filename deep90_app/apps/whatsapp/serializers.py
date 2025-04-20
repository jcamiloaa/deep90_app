from rest_framework import serializers
from .models import WhatsAppUser, Conversation, Message


class WhatsAppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppUser
        fields = '__all__'


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = '__all__'


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = '__all__'


class WebhookSerializer(serializers.Serializer):
    object = serializers.CharField()
    entry = serializers.ListField(child=serializers.DictField())