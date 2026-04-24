from validator import Validator


def make_good_wechat_article() -> str:
    return "你好朋友。今天我想跟你聊一个话题。你知道吗？很多人都忽视了这个细节。我觉得这件事特别值得思考。我们来看看。\n\n" * 40


def make_good_toutiao_article() -> str:
    return "你好。今天聊个事。你知道吗？很多人不懂这个。我来告诉你。\n\n" * 30


class TestAIMarkers:
    def test_ai_markers_too_high(self):
        text = "仿佛仿佛仿佛仿佛仿佛" + ("正常内容。" * 50)
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "AI_MARKER"]
        assert len(issues) > 0

    def test_ai_markers_normal(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "AI_MARKER"]
        assert len(issues) == 0

    def test_ai_markers_empty_content(self):
        result = Validator().validate("")
        issues = [i for i in result.issues if i.rule == "AI_MARKER"]
        assert len(issues) == 0


class TestForbiddenPhrases:
    def test_forbidden_phrase_detected(self):
        text = "这是毫无疑问的好产品。全场震惊。大家都说好。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "FORBIDDEN"]
        assert len(issues) >= 1

    def test_forbidden_phrase_absent(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "FORBIDDEN"]
        assert len(issues) == 0


class TestMetaPatterns:
    def test_meta_detected(self):
        text = "这篇文章的核心动机是帮助读者。叙事节奏也很重要。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "META"]
        assert len(issues) >= 1

    def test_meta_absent(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "META"]
        assert len(issues) == 0


class TestReportLanguage:
    def test_report_detected(self):
        text = "经分析当前局势后，综合考虑各种因素。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "REPORT"]
        assert len(issues) >= 1

    def test_report_absent(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "REPORT"]
        assert len(issues) == 0


class TestCollectivePatterns:
    def test_collective_detected(self):
        text = "在场之人无不震惊。众人异口同声地说好。一时间全场沸腾。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "COLLECTIVE"]
        assert len(issues) >= 1

    def test_collective_absent(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "COLLECTIVE"]
        assert len(issues) == 0


class TestSensitiveWords:
    def test_sensitive_detected(self):
        text = "这个产品全网最便宜，是独一无二的选择。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "SENSITIVE"]
        assert len(issues) >= 1

    def test_medical_sensitive(self):
        text = "这个药到病除的方子推荐给你。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "SENSITIVE"]
        assert len(issues) >= 1

    def test_short_word_no_false_positive(self):
        text = "这是一线城市的发展趋势。最好的选择是等待。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "SENSITIVE"]
        sensitive_texts = [i.excerpt for i in issues]
        assert "最好" not in sensitive_texts, f"'最好' 不应触发敏感词，但被触发：{sensitive_texts}"


class TestLengthCheck:
    def test_wechat_too_short(self):
        text = "很短的内容。"
        result = Validator().validate(text, platform="wechat")
        issues = [i for i in result.issues if i.rule == "LENGTH"]
        assert len(issues) >= 1

    def test_wechat_ok(self):
        text = make_good_wechat_article()
        assert len(text) >= 1500
        result = Validator().validate(text, platform="wechat")
        issues = [i for i in result.issues if i.rule == "LENGTH"]
        assert len(issues) == 0

    def test_toutiao_too_long(self):
        text = make_good_wechat_article()
        assert len(text) > 2000
        result = Validator().validate(text, platform="toutiao")
        issues = [i for i in result.issues if i.rule == "LENGTH"]
        assert len(issues) >= 1

    def test_toutiao_ok(self):
        text = make_good_toutiao_article()
        assert len(text) >= 800
        result = Validator().validate(text, platform="toutiao")
        issues = [i for i in result.issues if i.rule == "LENGTH"]
        assert len(issues) == 0


class TestLongParagraphs:
    def test_long_paragraphs_detected(self):
        long_para = "很长" * 200
        text = long_para + "\n\n" + long_para
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "LONG_PARA"]
        assert len(issues) >= 1

    def test_short_paragraphs_ok(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "LONG_PARA"]
        assert len(issues) == 0


class TestConsecutiveLe:
    def test_consecutive_le_detected(self):
        text = "我吃了饭了。他睡了觉了。天黑了。雨停了。花开了。鸟叫了。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "CONSECUTIVE_LE"]
        assert len(issues) >= 1

    def test_consecutive_le_ok(self):
        text = "我吃了饭。天空很蓝。他睡得很香。今天天气不错。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "CONSECUTIVE_LE"]
        assert len(issues) == 0


class TestAIFiller:
    def test_filler_too_many(self):
        text = "首先，我们要明白。其次，要注意的是。另外，还有一个点。此外，最后要说的是。在这个过程中，我们需要思考。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "AI_FILLER"]
        assert len(issues) >= 1

    def test_filler_few(self):
        text = "首先，我们要做的就是这件事。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "AI_FILLER"]
        assert len(issues) == 0


class TestRepetitive:
    def test_repetitive_detected(self):
        text = "重要的是第一点。重要的是第二点。重要的是第三点。"
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "REPETITIVE"]
        assert len(issues) >= 1

    def test_repetitive_ok(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "REPETITIVE"]
        assert len(issues) == 0


class TestExclamation:
    def test_exclamation_too_many(self):
        text = "太好看了！！！！" * 3
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "EXCLAMATION"]
        assert len(issues) >= 1

    def test_exclamation_ok(self):
        text = make_good_wechat_article()
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "EXCLAMATION"]
        assert len(issues) == 0


class TestMonotone:
    def test_monotone_detected(self):
        lines = ["这是一个段落。\n\n" for _ in range(6)]
        text = "".join(lines)
        result = Validator().validate(text)
        issues = [i for i in result.issues if i.rule == "MONOTONE"]
        assert len(issues) >= 1


class TestValidationScore:
    def test_perfect_score(self):
        text = "你好朋友。今天我想跟你聊一个话题。你知道吗？很多人都忽视了这个细节。我觉得这件事特别值得思考。我们来看看。\n\n你好朋友。今天我想跟你聊一个话题。你知道吗？很多人都忽视了这个细节。我觉得这件事特别值得思考。我们来看看。\n\n" * 25  + "这是一段。\n\n" + "这是一段更长的段落，包含更多文字来打破单调的模式。我们需要让段落长度有变化，这样才能避免被检测为过于单调。验证器会检查段落长度的变化情况。\n\n"
        assert len(text) >= 1500
        result = Validator().validate(text)
        assert result.score == 100, f"score={result.score}, issues={[(i.rule, i.description) for i in result.issues]}"

    def test_score_deducted_forbidden(self):
        text = "全场震惊。毫无疑问。"
        result = Validator().validate(text)
        assert result.score < 100
        assert result.passed is False

    def test_custom_sensitive_words(self):
        v = Validator(custom_sensitive=["自定义敏感词"])
        text = "这是一个自定义敏感词。"
        result = v.validate(text)
        issues = [i for i in result.issues if i.rule == "SENSITIVE"]
        assert len(issues) >= 1
