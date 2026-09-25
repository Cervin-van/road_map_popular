from rest_framework import serializers

from apps.locations.serializers import AuthorShortSerializer

from .models import Review, ReviewVote

VOTE_LABELS = {value: label for value, label in ReviewVote.Value.choices}


class ReviewSerializer(serializers.ModelSerializer):
    # Counters and my_vote are annotations from selectors.reviews_with_votes()
    author = AuthorShortSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    my_vote = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "location",
            "author",
            "rating",
            "text",
            "likes_count",
            "dislikes_count",
            "my_vote",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_my_vote(self, obj) -> str | None:
        return VOTE_LABELS.get(obj.my_vote)


class ReviewWriteSerializer(serializers.ModelSerializer):
    # rating range 1-5 comes from the model validators
    class Meta:
        model = Review
        fields = ["rating", "text"]
