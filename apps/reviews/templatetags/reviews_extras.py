from django import template

register = template.Library()


@register.simple_tag
def is_helpful_for(review, user):
    """指定ユーザーがそのレビューを参考になったマーク済みか"""
    if not user or not user.is_authenticated:
        return False
    return review.helpfuls.filter(user=user).exists()


@register.simple_tag
def helpful_count(review):
    return review.helpfuls.count()
