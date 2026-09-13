"""アンケート定義。survey_slug ごとに設問・選択肢・公開しきい値を持つ。

回答は apps.surveys.models.SurveyResponse.answers(JSON) に
{question_key: choice_value} で保存する。記事側は [survey slug="..."]
ショートコードで設問フォームと集計を描画する。
"""

SURVEYS = {
    "present-gift": {
        "title": "美顔器プレゼントの実体験アンケート",
        "intro": (
            "美顔器をプレゼントで「もらった／贈った」経験について、みなさんの声を"
            "募集しています。集まった回答は、このページで集計結果として公開します"
            "（回答は匿名・任意です）。"
        ),
        # 集計結果を公開し始める最小の有効回答数。これ未満は「集計中」と表示する。
        "threshold": 30,
        "questions": {
            "received": {
                "label": "美顔器をプレゼントでもらった経験はありますか？",
                "required": True,
                "choices": [("yes", "ある"), ("no", "ない")],
            },
            "received_feeling": {
                "label": "もらったとき、どう感じましたか？（もらった方）",
                "required": False,
                "choices": [
                    ("glad", "うれしかった"),
                    ("glad_but", "うれしかったが、使い方や置き場所に少し困った"),
                    ("unused", "自分には合わず、あまり使わなかった"),
                    ("other", "その他"),
                ],
            },
            "gave": {
                "label": "美顔器をプレゼントした経験はありますか？",
                "required": False,
                "choices": [("yes", "ある"), ("no", "ない")],
            },
            "gave_confirm": {
                "label": "贈る前に、相手の希望を確認しましたか？（贈った方）",
                "required": False,
                "choices": [
                    ("checked", "確認した"),
                    ("hinted", "それとなく聞いた"),
                    ("no", "確認しなかった"),
                ],
            },
        },
        "reason_label": "その理由や感想があれば教えてください（任意・公開前に内容を確認します）",
        # 公開する自由記述コメントの最大表示件数
        "reason_display_limit": 8,
    },
}


def get_survey(slug):
    return SURVEYS.get(slug)
