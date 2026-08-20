#!/usr/bin/env python3
"""Flag unqualified absolute claims in note prose.

This is a review gate, not a grammar checker.  It reports the small set of
terms that commonly turn a bounded observation into an unsupported universal
claim.  Negated/conditional/evidence-bearing sentences are kept valid, while
the output gives a concrete rewrite suggestion for the remaining unique lines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass

from notes_utils import infer_note_type, markdown_files, read_text, rel

TARGETS = ("首次提出", "必然", "完全", "解决", "保证", "显著提升")
SKIP_TYPES = {
    "agent_rule",
    "coverage_audit",
    "global_coverage_audit",
    "source_manifest",
    "source_manifest_history",
    "template",
    "vault_audit",
}
SKIP_NAME_RE = re.compile(r"(^|/)99_|全仓例题索引|source_manifest", re.I)
FENCE_RE = re.compile(r"^\s*```")
WIKILINK_RE = re.compile(r"(?P<embed>!)?\[\[(?P<body>[^\]\n]+)\]\]")


def mask_inline_code(line: str) -> str:
    """Blank CommonMark code spans without treating shorter ticks as closes.

    A code span opens and closes with runs of the same number of backticks.
    Scanning runs (rather than using ```[^`]*``` ``) keeps prose such as
    ``code ` [[x]]`` out of the language-claim audit while still allowing a
    shorter backtick inside the span.
    """

    chars = list(line)
    index = 0
    length = len(line)
    while index < length:
        if line[index] != "`":
            index += 1
            continue
        opening_end = index
        while opening_end < length and line[opening_end] == "`":
            opening_end += 1
        run = line[index:opening_end]
        closing = opening_end
        while closing < length:
            if line[closing] != "`":
                closing += 1
                continue
            closing_end = closing
            while closing_end < length and line[closing_end] == "`":
                closing_end += 1
            if closing_end - closing == len(run):
                break
            closing = closing_end
        if closing >= length:
            index = opening_end
            continue
        end = closing + len(run)
        chars[index:end] = [" "] * (end - index)
        index = end
    return "".join(chars)


def visible_wikilink_text(line: str) -> str:
    """Replace wikilinks with the text visible to the reader.

    Aliased links expose only the label, so a term in both target and label is
    audited once.  Bare links expose the target basename and optional heading;
    embedded-note or image targets are blanked because their filenames are not
    visible prose on the containing line.
    """

    def replace(match: re.Match[str]) -> str:
        if match.group("embed"):
            return " " * len(match.group(0))
        body = match.group("body")
        if "|" in body:
            visible = body.split("|", 1)[1]
        else:
            target, _, heading = body.partition("#")
            basename = target.rsplit("/", 1)[-1]
            visible = f"{basename}#{heading}" if basename and heading else basename or heading
        return f" {visible.strip()} "

    return WIKILINK_RE.sub(replace, line)

# These are technical terms whose “完全” is a definition rather than a claim
# about a method's success.
TECHNICAL_COMPLETE = re.compile(
    r"(?:完全(?:图|二叉树|匹配|平方|积分|连接|随机|背包|独立|可观测|竞争|限定|数据|序列|码|相同|一致|错位|均匀|没有|不用|基于|关闭|覆盖|重写|交互|一样|丢掉|错误|真实|可用|稳定|正确率)|shape\s*完全正确)",
)
NEGATED_CONTEXT = re.compile(
    r"(?:不(?:一定|必然|能|会|等于|可|代表|保证|提供|再保证|成立|在|意味着|自动|构成|单独|表示|等同|具备|支持|受保证)|"
    r"不是|并不是|没有|无须|未必|并非|尚未|无法|不能|不可|未提供|不提供|不足以|并无|不受保证|无保证|只保证|"
    r"非(?:充分|必要)|而非|不承诺|通常|一般|可能|有助于|往往|部分|仅)",
)
CONDITIONAL_CONTEXT = re.compile(
    r"(?:在[^。！？\n]{0,60}(?:条件|前提|假设|设置|场景|范围|约束|数据|参数|环境)[^。！？\n]{0,40}(?:下|中|时|内)|"
    r"(?:若|如果|当|只要|除非|只有)[^。！？\n]{1,100}|"
    r"(?:满足|给定|基于|依赖(?:于)?|取决于)[^。！？\n]{0,60}(?:则|时|下|中|可以|能够|保证|成立|有效)|"
    r"(?:非负|有界|有限|无环|可终止|允许重开|满足[^。！？\n]{0,30}(?:约束|条件)|"
    r"(?:[<>=≤≥]|不等于|等于)[^。！？\n]{0,80}(?:则|可保证|能够保证))[^。！？\n]{0,60}(?:保证|可|能够|成立|有效)|"
    r"(?:才能|必须[^。！？\n]{0,20}保证)[^。！？\n]{0,100}(?:正确|成立|一致|有效|完成|成功|回放|保证)|"
    r"(?:条件是|前提是|取决于|依赖于))",
)
QUESTION_CONTEXT = re.compile(r"(?:[?？]|是否|能否|可否|为什么|为何|如何|怎样|吗(?:[，。！？]|$))")
FORMAL_CATEGORY_CONTEXT = re.compile(
    r"(?:定理|证明|推论|公理|定义|恒等|等式|正确性|不变量|充分条件|必要条件|"
    r"协议|规范|线性化|串行化|形式化|可判定|等价性|安全性质|数学|公式|收敛|"
    r"无损连接|故障恢复|停机|威胁假设|下界|最小解|抽屉原理|DFA|分母|分子|"
    r"归一化|概率|求和|积分|最短路|PSD|内积|Softmax|softmax|mask|barrier|"
    r"内存可见性|按序交付|事务补偿|交换性|calibration|KKT|Slater|量化|差分隐私|"
    r"相邻数据集|输出分布|任意合法|合法实例|抽屉原理|最小代价|相等|最优性|"
    r"容量|元素数量|iterator|引用|生命周期|原子性|线程|内存|正确状态|可行域|"
    r"无损|最坏情况|最小可行|token序列|合法 token|padding|embedding|失效|shape|dim|"
    r"正值|正数|scale|Bernoulli|硬约束|算法结束|答案正确|自动机|状态集|初态|"
    r"bitwise|exactly-once|checkpoint|读写顺序|写写顺序|WAW|WAR|\\sum|w\(i,j\)|"
    r"路径合法|合法性|候选边|邻接关系)",
)
FORMAL_NOUN = re.compile(
    r"(?:质量|安全|一致性|可靠性|可用性|性能|责任|服务水平|风险|形式化|协议|保证程度|保证级别|最优性)保证"
)
BROADER_SOLUTION_RE = re.compile(
    r"(?:完全|彻底|根本|有效|成功|彻底地|无条件|一劳永逸|"
    r"解决(?:所有|全部|任何|一切|梯度消失|梯度爆炸|过拟合|数据泄漏|分布漂移|"
    r"通用问题|普遍问题|整体性能))"
)
DEFINITIONAL_CERTAINTY = re.compile(
    r"(?:数学|定义|公理|定理|证明|恒等|等式)[^。！？\n]{0,16}必然|"
    r"必然[^。！？\n]{0,16}(?:定义|公理|定理|证明|恒等|等式)",
)
EVIDENCE_RE = re.compile(
    r"(?:实验|结果|指标|数据|样本|对比|消融|报告|统计|百分点|%|PSNR|SSIM|AUC|p\s*[<=>]|论文|作者|参考|引用|doi|https?://|\[[^\]]+\]\()",
    re.I,
)
@dataclass(frozen=True)
class Issue:
    file: str
    line: int
    term: str
    sentence: str
    suggestion: str
    high_confidence: bool
    confidence: str
    category: str


def deduplicate_issues(issues: list[Issue]) -> list[Issue]:
    """Keep the first issue for each rendered sentence-level claim."""

    unique: list[Issue] = []
    seen: set[tuple[str, int, str, str]] = set()
    for issue in issues:
        key = (issue.file, issue.line, issue.term, issue.sentence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(issue)
    return unique


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(mark, 0, start) for mark in "。！？\n")
    right_candidates = [text.find(mark, end) for mark in "。！？\n"]
    right_candidates = [value for value in right_candidates if value >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    return text[left + 1 : right + 1].strip()


def _suggestion(term: str, category: str = "ENGINEERING_PROMISE") -> str:
    if category == "QUESTION_OR_QUOTE":
        return "这是问题或引文语境；不应把其中的绝对措辞当成作者断言。"
    if category == "NEGATED_GUARANTEE":
        return "句子已经明确否定或限制该断言；保留原边界，并确认否定对象指向清楚。"
    if category == "CONDITIONAL_GUARANTEE":
        return "保留条件、前提和适用范围；若条件并不充分，应补充失败边界或验证方式。"
    if category == "FORMAL_GUARANTEE":
        return "这是定义、定理、协议或公式语境；保留形式化结论，并明确成立前提，不要改写成经验性表述。"
    if category == "POLICY_OR_LEGAL_CLAIM":
        return "补充适用地区、生效时间和官方依据，避免把政策性结论写成无条件的普遍事实。"
    return {
        "首次提出": "改为“论文将……作为一种方法/在本文中提出”，并附原论文或引用；只有可核查文献证据时才保留“首次”。",
        "必然": "补充成立条件和适用范围，或改为“通常/可能/在该条件下”。",
        "完全": "说明是定义性术语还是性能断言；性能表述可改为“在给定设置下较充分/仍有边界”。",
        "解决": "改为“缓解/有助于处理/在该设置下改善”，并写明未覆盖的失败条件。",
        "保证": "说明保证的对象、成立前提和验证方式；若只是设计目标，改为“用于/旨在”，不要用泛化措辞掩盖边界。",
        "显著提升": "给出数据集、指标和对照；缺少统计证据时改为“在该实验设置下提升”。",
    }[term]


def _high_confidence(term: str, sentence: str) -> bool:
    """Identify only claims that should block a strict delivery gate."""

    if "?" in sentence or "？" in sentence:
        return False
    if NEGATED_CONTEXT.search(sentence) or CONDITIONAL_CONTEXT.search(sentence):
        return False
    if term in {"首次提出", "显著提升"}:
        return not EVIDENCE_RE.search(sentence)
    if term == "必然":
        # Mathematical definitions/theorems and explicit questions are not
        # prose overclaims; otherwise “必然” needs a stated condition.
        if re.search(r"(?:已知|概率为 ?1|定理|证明|推论|不等式|有限|正数|任意合法|数学|条件|假设|通常|可能|不表示|公式|\$|=)", sentence):
            return False
        return True
    if term == "完全":
        if re.search(r"(?:很难|难以|不(?:能|会)|不是|并非|没有)", sentence):
            return False
        return bool(re.search(r"完全(?:解决|保证|提升|消除|避免|正确|可靠)", sentence))
    if term == "解决":
        return bool(re.search(r"解决(?:梯度消失|梯度爆炸|所有|全部|任何|一切|通用|普遍|整体性能)", sentence))
    if term == "保证":
        if re.search(r"(?:不(?:能|会)|依赖|前提|条件|只|不自动|特定|应|需|必须|需要|理论|定义|协议|算法|硬约束|公式|\$|=|通常|可能|有助于|并无)", sentence):
            return False
        return bool(re.search(r"保证(?:所有|全部|任何|完全|不存在|成功|最佳|覆盖关键)", sentence))
    return False


def classify_claim(term: str, sentence: str) -> str:
    """Classify a candidate without treating every categorical word alike."""

    if QUESTION_CONTEXT.search(sentence) or re.search(r"[“‘\"'].*[”’\"']", sentence):
        return "QUESTION_OR_QUOTE"
    if NEGATED_CONTEXT.search(sentence):
        return "NEGATED_GUARANTEE"
    if CONDITIONAL_CONTEXT.search(sentence):
        return "CONDITIONAL_GUARANTEE"
    if (
        FORMAL_CATEGORY_CONTEXT.search(sentence)
        or FORMAL_NOUN.search(sentence)
        or DEFINITIONAL_CERTAINTY.search(sentence)
    ):
        return "FORMAL_GUARANTEE"
    if re.search(r"(?:条件|前提|假设|设置|场景|范围|依赖|取决于)", sentence):
        return "CONDITIONAL_GUARANTEE"
    if re.search(r"(?:法律|法规|政策|监管|合规|法定)", sentence):
        return "POLICY_OR_LEGAL_CLAIM"
    if term in {"首次提出", "显著提升"}:
        return "EMPIRICAL_OVERCLAIM"
    if term in {"解决", "保证", "完全", "必然"}:
        return "ENGINEERING_PROMISE"
    return "MANUAL_REVIEW"


def audit_line(line: str, line_number: int, relative_file: str) -> list[Issue]:
    """Audit one prose line; exported for focused regression tests."""

    # Inline code is executable syntax/identifiers, not explanatory prose;
    # wikilink targets hidden behind aliases must not be counted as prose.
    prose = visible_wikilink_text(mask_inline_code(line))
    issues: list[Issue] = []
    for match in re.finditer("|".join(map(re.escape, TARGETS)), prose):
        term = match.group(0)
        prefix = prose[max(0, match.start() - 4) : match.start()]
        suffix = prose[match.end() : match.end() + 24]
        if term == "完全" and (prefix.endswith(("不", "非", "没")) or suffix.startswith(("不", "无"))):
            continue
        if term == "完全" and not re.search(r"完全(?:解决|恢复|保证|提升|消除|避免|正确|可靠|无|没有)", prose[max(0, match.start() - 2) : match.end() + 12]):
            continue
        if term == "完全" and TECHNICAL_COMPLETE.search(prose[max(0, match.start() - 20) : match.end() + 16]):
            continue
        sentence = _sentence(prose, match.start(), match.end())
        category = classify_claim(term, sentence)
        if category == "QUESTION_OR_QUOTE":
            continue
        # Imperative/prescriptive phrases state a requirement or procedure;
        # they do not claim that the requirement has already been satisfied.
        if term == "保证" and re.search(r"(?:先|应|需|必须|要|为|以|只|至少)\s*$", prefix):
            continue
        if term == "保证" and FORMAL_NOUN.search(sentence):
            continue
        if term == "必然" and DEFINITIONAL_CERTAINTY.search(sentence):
            continue
        if category in {
            "NEGATED_GUARANTEE",
            "CONDITIONAL_GUARANTEE",
            "FORMAL_GUARANTEE",
        }:
            continue
        if term == "解决":
            # Headings and problem statements describe the target, not a
            # claim that a method solved every instance.  Keep the stricter
            # check for bare performance assertions such as “解决梯度消失”.
            if re.search(
                r"(?:要解决|需解决|需要解决|用于解决|可以帮助解决|能够帮助解决|旨在解决|针对解决|解决的是|解决什么|解决方法|解决方案|解决路径|解决框架)",
                sentence,
            ):
                continue
            if not BROADER_SOLUTION_RE.search(sentence):
                continue
        # “保证金” is a financial noun, not an absolute claim about a
        # method.  Other uses must pass the explicit negation/condition and
        # universal-scope checks above; generic words such as “系统/成功”
        # must not suppress an unconditional guarantee.
        if term == "保证" and suffix.startswith("金"):
            continue
        if term == "首次提出" and EVIDENCE_RE.search(sentence):
            continue
        if term == "显著提升" and EVIDENCE_RE.search(sentence):
            continue
        high_confidence = _high_confidence(term, sentence)
        category = classify_claim(term, sentence)
        issues.append(
            Issue(
                relative_file,
                line_number,
                term,
                sentence,
                _suggestion(term, category),
                high_confidence,
                "high" if high_confidence else "review",
                category,
            )
        )
    return issues


def scan_notes() -> list[Issue]:
    issues: list[Issue] = []
    for path in markdown_files():
        if SKIP_NAME_RE.search(rel(path)) or infer_note_type(path) in SKIP_TYPES:
            continue
        in_fence = False
        for number, line in enumerate(read_text(path).splitlines(), start=1):
            if FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if line.lstrip().startswith("#"):
                continue
            issues.extend(audit_line(line, number, rel(path)))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="fail when an unqualified claim is found")
    args = parser.parse_args()
    issues = deduplicate_issues(scan_notes())
    payload = {
        "terms": list(TARGETS),
        "issues": [asdict(issue) for issue in issues],
        "issue_count": len(issues),
        "high_confidence_count": sum(issue.high_confidence for issue in issues),
        "category_counts": {
            category: sum(issue.category == category for issue in issues)
            for category in sorted({issue.category for issue in issues})
        },
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"language_issues {len(issues)}")
        print(f"language_high_confidence {sum(issue.high_confidence for issue in issues)}")
        for issue in issues[:100]:
            label = "HIGH" if issue.high_confidence else "REVIEW"
            print(f"{label} {issue.file}:{issue.line} [{issue.term}/{issue.category}] {issue.sentence}")
            print(f"  SUGGEST {issue.suggestion}")
    return 1 if args.strict and any(issue.high_confidence for issue in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
