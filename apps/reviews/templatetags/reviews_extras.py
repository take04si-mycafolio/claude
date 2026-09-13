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


@register.simple_tag
def has_reported_for(review, user):
    """指定ユーザーがそのレビューを通報済みか（通報ボタンの表示切替に使う）。"""
    if not user or not user.is_authenticated:
        return False
    return review.reports.filter(reporter=user).exists()
