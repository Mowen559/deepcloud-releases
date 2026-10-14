"""
提取器测试

不联网、不启浏览器：被测的是「规则怎么落到记录上」与「取不到值时怎么兜底」，
这些都是纯逻辑，用 Selector 直接喂 HTML 即可覆盖。

真实抓取与 adaptive 自愈已用运行中的服务实测（见台账 #15），
那类验证依赖外网与 Chromium，不适合进单测。
"""

from scrapling import Selector

from app.extractor import Extractor
from app.models import FieldRule

HTML = """
<html><body>
  <ul class="list">
    <li class="item">
      <a class="link" href="/job/1">Java 工程师</a>
      <span class="salary">20,000</span>
      <span class="city">杭州</span>
    </li>
    <li class="item">
      <a class="link" href="https://other.com/job/2">Python 工程师</a>
      <span class="salary">25,000</span>
    </li>
  </ul>
</body></html>
"""


def page():
    return Selector(HTML, url="https://example.com/list")


def rule(target, selector, **kw):
    return FieldRule(targetField=target, selector=selector, **kw)


class TestContainerAndFields:

    def test_每个容器元素产出一条记录(self):
        records, warnings = Extractor().extract(
            page(), "ul.list li.item", [rule("title", "a.link")], adaptive=False
        )
        assert [r["title"] for r in records] == ["Java 工程师", "Python 工程师"]
        assert warnings == []

    def test_容器留空时整页视为一条记录(self):
        # 详情页场景：没有列表容器，整页就是一条数据
        records, _ = Extractor().extract(
            page(), None, [rule("title", "a.link")], adaptive=False
        )
        assert len(records) == 1
        assert records[0]["title"] == "Java 工程师"

    def test_容器选择器失配时给出可操作告警(self):
        records, warnings = Extractor().extract(
            page(), "ul.nonexistent li", [rule("title", "a.link")], adaptive=False
        )
        assert records == []
        assert any("未匹配到任何元素" in w for w in warnings)

    def test_取不到且无兜底值时不落key(self):
        # 第二条没有 .city，该字段应当缺席而不是写成空串——
        # 否则下游无法区分「没这个字段」和「字段值为空」。
        # 带上 title 是必要的：全空记录会被丢弃，那样第二条根本不会出现
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("title", "a.link"), rule("city", "span.city")], adaptive=False
        )
        assert records[0]["city"] == "杭州"
        assert "city" not in records[1]

    def test_全空记录被丢弃(self):
        # 容器匹配到了但一个字段都没取到，落库只会得到空行
        records, _ = Extractor().extract(
            page(), "ul.list li.item", [rule("x", "span.nonexistent")], adaptive=False
        )
        assert records == []

    def test_兜底值在取不到时生效(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("city", "span.city", defaultValue="未知")], adaptive=False
        )
        assert records[1]["city"] == "未知"


class TestValueExtraction:

    def test_相对链接补全为绝对地址(self):
        # 站点里大量是相对路径，不补全下游拿到 /job/1 无法直接使用
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("url", "a.link", extractAttr="href")], adaptive=False
        )
        assert records[0]["url"] == "https://example.com/job/1"

    def test_已是绝对地址的链接不被改写(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("url", "a.link", extractAttr="href")], adaptive=False
        )
        assert records[1]["url"] == "https://other.com/job/2"

    def test_html取值返回标签内容(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("raw", "a.link", extractAttr="html")], adaptive=False
        )
        assert "Java 工程师" in records[0]["raw"]


class TestRegex:

    def test_正则二次截取(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("num", "span.salary", regex=r"(\d+),(\d+)", regexGroup=1)],
            adaptive=False,
        )
        assert records[0]["num"] == "20"

    def test_组序号越界时退回整个匹配串(self):
        # 规则写错不该丢数据
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("num", "span.salary", regex=r"(\d+),(\d+)", regexGroup=9)],
            adaptive=False,
        )
        assert records[0]["num"] == "20,000"

    def test_正则不匹配时该字段缺席(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("title", "a.link"), rule("num", "span.salary", regex=r"([a-z]+)")],
            adaptive=False,
        )
        assert "num" not in records[0]
        assert records[0]["title"] == "Java 工程师"

    def test_非法正则不抛错而是返回原值(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [rule("num", "span.salary", regex=r"([unclosed")], adaptive=False
        )
        assert records[0]["num"] == "20,000"

    def test_REGEX类型对容器全文匹配(self):
        # 这种类型不需要选择器。容器元素的 .text 是空串（文字在后代节点里），
        # 所以这条同时守着「取文本时回退到 get_all_text」那个实现
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [FieldRule(targetField="city", type="REGEX", regex=r"(杭州)")],
            adaptive=False,
        )
        assert records[0]["city"] == "杭州"

    def test_文字在内层元素时也能取到(self):
        # 用户常写容器级选择器而文字在子元素里，这时必须回退到后代全文
        records, _ = Extractor().extract(
            page(), "ul.list", [rule("all", "li.item")], adaptive=False
        )
        assert "Java 工程师" in records[0]["all"]


class TestRobustness:

    def test_单个字段选择器出错不影响整条记录(self):
        records, warnings = Extractor().extract(
            page(), "ul.list li.item",
            [rule("title", "a.link"), rule("bad", "a[[[")], adaptive=False
        )
        assert records[0]["title"] == "Java 工程师"
        assert any("bad" in w for w in warnings)

    def test_xpath类型可用(self):
        records, _ = Extractor().extract(
            page(), "ul.list li.item",
            [FieldRule(targetField="title", type="XPATH", selector=".//a")],
            adaptive=False,
        )
        assert records[0]["title"] == "Java 工程师"
