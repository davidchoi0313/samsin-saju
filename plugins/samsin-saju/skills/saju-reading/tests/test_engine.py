# -*- coding: utf-8 -*-
"""
test_engine.py — 만세력 엔진 골든/엣지 테스트 (TDD 빨강 우선)

설계서 DESIGN.md §7.1 검증값을 골든 기대값으로 고정한다.
실행:  python3 test_engine.py
표준 라이브러리 unittest만 사용(외부 테스트 러너 불요 — 샌드박스 견고성).
"""
import sys
import os
import json
import subprocess
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import saju_engine  # noqa: E402


def golden_card():
    """골든 입력: 1990-03-15 양력 묘시 남."""
    return saju_engine.build_card({
        "gender": "male",
        "calendar": "solar",
        "birthDate": "1990-03-15",
        "birthTime": "mau",
        "birthLongitude": 127.5,
        "earlyLateZiShi": "standard",
    })


class TestVendoredRuntime(unittest.TestCase):
    """공개·모바일 런타임에서 외부 설치 없이 계산되는지 확인."""

    def test_clean_python_uses_bundled_lunar_source(self):
        """site-packages와 PYTHONPATH 없이도 번들 v1.4.8로 골든 입력을 산출한다."""
        engine_path = os.path.realpath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "saju_engine.py")
        )
        probe = r"""
import json
import os
import runpy
import sys

engine = runpy.run_path(sys.argv[1], run_name="vendored_runtime_probe")
card = engine["build_card"]({
    "gender": "male",
    "calendar": "solar",
    "birthDate": "1990-03-15",
    "birthTime": "mau",
    "birthLongitude": 127.5,
    "earlyLateZiShi": "standard",
})
import lunar_python
print(json.dumps({
    "yearPillar": card["pillars"]["year"]["gan"] + card["pillars"]["year"]["zhi"],
    "lunarModule": os.path.realpath(lunar_python.__file__),
}, ensure_ascii=False))
"""
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": "",
            "PYTHONNOUSERSITE": "1",
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        })
        # -X utf8: -I 는 환경변수를 무시하므로 PYTHONIOENCODING 이 안 먹는다.
        # 이게 없으면 한국어 Windows 에서 자식 stdout 이 cp949 로 잡혀
        # 간지 한자를 utf-8 로 읽다가 UnicodeDecodeError 가 난다.
        completed = subprocess.run(
            [sys.executable, "-I", "-S", "-X", "utf8", "-c", probe, engine_path],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
        )
        result = json.loads(completed.stdout)
        expected_vendor = os.path.realpath(
            os.path.join(
                os.path.dirname(engine_path),
                "vendor",
                "lunar-python-1.4.8",
                "lunar_python",
            )
        )

        self.assertEqual(result["yearPillar"], "庚午")
        self.assertEqual(
            os.path.commonpath([result["lunarModule"], expected_vendor]),
            expected_vendor,
        )


class TestGoldenCase(unittest.TestCase):
    """설계서 §7.1 골든 케이스."""

    @classmethod
    def setUpClass(cls):
        cls.card = golden_card()

    def test_pillars_8char(self):
        """사주팔자: 庚午 己卯 己卯 丁卯."""
        p = self.card["pillars"]
        self.assertEqual(p["year"]["gan"] + p["year"]["zhi"], "庚午")
        self.assertEqual(p["month"]["gan"] + p["month"]["zhi"], "己卯")
        self.assertEqual(p["day"]["gan"] + p["day"]["zhi"], "己卯")
        self.assertEqual(p["hour"]["gan"] + p["hour"]["zhi"], "丁卯")

    def test_day_master(self):
        """일간 己土 음토."""
        dm = self.card["dayMaster"]
        self.assertEqual(dm["gan"], "己")
        self.assertEqual(dm["element"], "土")
        self.assertEqual(dm["yinYang"], "陰")

    def test_ten_gods(self):
        """십신: 년 상관 / 월 비견 / 시 편인 / 일지 칠살."""
        tg = self.card["tenGods"]
        self.assertEqual(tg["year"], "상관")
        self.assertEqual(tg["month"], "비견")
        self.assertEqual(tg["hour"], "편인")
        self.assertIn("칠살", tg["dayBranchHidden"])

    def test_napyin_year(self):
        """납음(년주): 노방토(路旁土)."""
        self.assertEqual(self.card["napEum"]["year"], "路旁土")

    def test_taeyuan_minggong_shengong(self):
        """태원 庚午 / 명궁 丁亥 / 신궁 癸未."""
        self.assertEqual(self.card["taeWon"], "庚午")
        self.assertEqual(self.card["mingGong"], "丁亥")
        self.assertEqual(self.card["shenGong"], "癸未")

    def test_gongmang(self):
        """공망(일주 기준): 申酉."""
        gm = [s for s in self.card["majorShinsal"] if s["name"] == "공망"]
        self.assertTrue(gm, "공망 항목이 majorShinsal에 있어야 함")
        self.assertEqual(gm[0]["pos"], "申酉")

    def test_daewoon_start_forward(self):
        """대운: 7세 시작, 순행."""
        dw = self.card["daewoon"]
        self.assertEqual(dw["startAge"], 7)
        self.assertTrue(dw["forward"])

    def test_daewoon_list(self):
        """대운 리스트: 8세 庚辰 / 18세 辛巳 / 28세 壬午 / 38세 癸未."""
        lst = self.card["daewoon"]["list"]
        first4 = {(d["fromAge"], d["gan"] + d["zhi"]) for d in lst[:4]}
        self.assertIn((8, "庚辰"), first4)
        self.assertIn((18, "辛巳"), first4)
        self.assertIn((28, "壬午"), first4)
        self.assertIn((38, "癸未"), first4)

    def test_five_elements_count(self):
        """오행 분포(지장간 여기·중기·정기 전체 반영): 木6 火3 土3 金1 水0.

        변경 전(천간+지지 본기): 木3 火2 土2 金1 水0.
        변경 후(천간+지장간 전체): 卯x3 지장간 甲乙 -> 木 급증, 午 지장간 丙己丁 반영.
        水는 午·卯에 水 지장간이 없어 여전히 0(missing 유지).
        """
        fe = self.card["fiveElements"]
        self.assertEqual(fe["count"], {"木": 6, "火": 3, "土": 3, "金": 1, "水": 0})
        self.assertEqual(fe["missing"], ["水"])
        self.assertEqual(fe["dominant"], ["木"])
        self.assertEqual(fe["strength"], "중화")

    def test_five_elements_hidden_breakdown(self):
        """지장간 분해(fiveElements.hiddenStems): 년지 午=丙己丁 / 월지 卯=甲乙."""
        hs = {h["position"]: h for h in self.card["fiveElements"]["hiddenStems"]}
        o = hs["year"]
        self.assertEqual(o["branch"], "午")
        self.assertEqual(
            [(s["role"], s["gan"], s["element"]) for s in o["stems"]],
            [("여기", "丙", "火"), ("중기", "己", "土"), ("정기", "丁", "火")],
        )
        m = hs["month"]
        self.assertEqual(
            [(s["role"], s["gan"]) for s in m["stems"]],
            [("여기", "甲"), ("정기", "乙")],
        )

    def test_yongshin_candidates_are_actual_elements(self):
        """용신 후보 element에는 오행값만 들어가 사용자 번역표와 어긋나지 않는다."""
        candidates = self.card["yongshin"]["candidates"]
        self.assertTrue(candidates)
        self.assertTrue(
            all(item["element"] in {"木", "火", "土", "金", "水"} for item in candidates)
        )
        self.assertIn(
            {"type": "보완", "element": "水", "reason": "중화 사주에서 비어 있는 水 오행을 보완 후보로 본다"},
            candidates,
        )

    def test_sewoon_2027(self):
        """세운(2027): 丁未."""
        sw = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "1990-03-15", "birthTime": "mau",
            "sewoonYear": 2027,
        })["sewoon"]
        self.assertEqual(sw["currentYear"], 2027)
        self.assertEqual(sw["ganZhi"], "丁未")

    def test_disclaimer_field_absent_in_engine(self):
        """엔진 산출 카드에는 면책이 들어가지 않는다(면책은 AI 해석층 강제)."""
        self.assertNotIn("disclaimer", self.card)


GAN_ORDER = "甲乙丙丁戊己庚辛壬癸"
ZHI_ORDER = "子丑寅卯辰巳午未申酉戌亥"
MONTH_ZHI_ORDER = "寅卯辰巳午未申酉戌亥子丑"
TEN_GODS = {
    "비견", "겁재", "식신", "상관", "편재",
    "정재", "칠살", "정관", "편인", "정인",
}


def sewoon_of(year, **overrides):
    payload = {
        "gender": "male", "calendar": "solar",
        "birthDate": "1990-03-15", "birthTime": "mau",
        "sewoonYear": year,
    }
    payload.update(overrides)
    return saju_engine.build_card(payload)["sewoon"]


class TestSewoonMonthly(unittest.TestCase):
    """세운 월운: 카드에 월별 근거가 실제로 있어야 한다.

    스타터 프롬프트가 '월별로'를 약속하는데 연간 간지만 있으면 AI가
    없는 달을 지어내게 된다. 그 구멍을 막는 자리다.
    """

    @classmethod
    def setUpClass(cls):
        cls.monthly = sewoon_of(2026)["monthly"]

    def test_twelve_months(self):
        self.assertEqual(12, len(self.monthly))
        self.assertEqual(list(range(1, 13)), [m["index"] for m in self.monthly])

    def test_ganzhi_format(self):
        for month in self.monthly:
            ganzhi = month["ganZhi"]
            self.assertEqual(2, len(ganzhi), ganzhi)
            self.assertIn(ganzhi[0], GAN_ORDER, ganzhi)
            self.assertIn(ganzhi[1], ZHI_ORDER, ganzhi)

    def test_month_branches_follow_jeolgi_order(self):
        """월지는 입춘의 寅부터 순서대로다. 양력 달과 경계가 다르다."""
        self.assertEqual(
            list(MONTH_ZHI_ORDER),
            [month["ganZhi"][1] for month in self.monthly],
        )

    def test_stems_advance_through_sixty_cycle(self):
        for earlier, later in zip(self.monthly, self.monthly[1:]):
            expected = GAN_ORDER[(GAN_ORDER.index(earlier["ganZhi"][0]) + 1) % 10]
            self.assertEqual(expected, later["ganZhi"][0])

    def test_first_month_starts_at_ipchun(self):
        first = self.monthly[0]
        self.assertEqual("2026-02-04", first["startDate"])
        self.assertEqual("2027-02-04", self.monthly[-1]["endDate"])

    def test_periods_are_contiguous(self):
        for earlier, later in zip(self.monthly, self.monthly[1:]):
            self.assertEqual(earlier["endDate"], later["startDate"])

    def test_ten_god_is_relative_to_day_master(self):
        for month in self.monthly:
            self.assertIn(month["tenGod"], TEN_GODS, month)

    def test_ten_god_matches_vendor_for_natal_stems(self):
        """일간 기준 십신 규칙을 벤더 라이브러리 산출과 대조한다."""
        card = saju_engine.build_card({
            "gender": "female", "calendar": "solar",
            "birthDate": "1988-11-02", "birthTime": "yu",
        })
        day_gan = card["pillars"]["day"]["gan"]
        for position in ("year", "month", "hour"):
            self.assertEqual(
                card["tenGods"][position],
                saju_engine._ten_god_for_gan(
                    day_gan, card["pillars"][position]["gan"]
                ),
                position,
            )

    def test_elements_match_ganzhi(self):
        for month in self.monthly:
            self.assertEqual(
                saju_engine.GAN_ELEMENT[month["ganZhi"][0]], month["ganElement"]
            )
            self.assertEqual(
                saju_engine.ZHI_MAIN_ELEMENT[month["ganZhi"][1]], month["zhiElement"]
            )

    def test_determinism(self):
        self.assertEqual(self.monthly, sewoon_of(2026)["monthly"])

    def test_different_year_gives_different_pillars(self):
        other = sewoon_of(2027)["monthly"]
        self.assertNotEqual(
            [m["ganZhi"] for m in self.monthly], [m["ganZhi"] for m in other]
        )

    def test_hour_unknown_still_has_monthly(self):
        monthly = sewoon_of(2026, birthTime="unknown")["monthly"]
        self.assertEqual(12, len(monthly))

    def test_annual_ten_god_present(self):
        self.assertIn(sewoon_of(2026)["tenGod"], TEN_GODS)


class TestEdgeCases(unittest.TestCase):
    """엣지 케이스: 깨지지 않음 확인."""

    def test_ipchun_boundary_before(self):
        """입춘 경계 전(2000-02-04): 전년 간지(己卯) 유지."""
        card = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "2000-02-04", "birthTime": "o",
        })
        y = card["pillars"]["year"]
        self.assertEqual(y["gan"] + y["zhi"], "己卯")

    def test_ipchun_boundary_after(self):
        """입춘 경계 후(2000-02-05): 당년 간지(庚辰)로 전환."""
        card = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "2000-02-05", "birthTime": "o",
        })
        y = card["pillars"]["year"]
        self.assertEqual(y["gan"] + y["zhi"], "庚辰")

    def test_hour_unknown(self):
        """시 모름: 시주 null, 깨지지 않음."""
        card = saju_engine.build_card({
            "gender": "female", "calendar": "solar",
            "birthDate": "1990-03-15", "birthTime": "unknown",
        })
        self.assertIsNone(card["pillars"]["hour"])
        self.assertEqual(card["meta"]["hourKnown"], False)
        self.assertEqual(card["tenGods"].get("hour"), "시 미상")

    def test_lunar_leap_month(self):
        """음력 윤달(2020 윤4월 15일): 깨지지 않고 산출."""
        card = saju_engine.build_card({
            "gender": "male", "calendar": "lunar", "isLeapMonth": True,
            "birthDate": "2020-04-15", "birthTime": "o",
        })
        self.assertEqual(card["pillars"]["year"]["gan"] + card["pillars"]["year"]["zhi"], "庚子")
        self.assertEqual(card["meta"]["solarDate"], "2020-06-06")

    def test_compatibility_two_people(self):
        """궁합 2인: compatibility 필드 산출."""
        result = saju_engine.build_compatibility(
            {"gender": "male", "calendar": "solar", "birthDate": "1990-03-15", "birthTime": "mau"},
            {"gender": "female", "calendar": "solar", "birthDate": "1992-07-20", "birthTime": "yu"},
        )
        self.assertIn("personA", result)
        self.assertIn("personB", result)
        self.assertIn("compatibility", result)
        self.assertIn("dayGanRelation", result["compatibility"])

    def test_today_fortune(self):
        """오늘의운세: today 필드(일진) 산출."""
        card = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "1990-03-15", "birthTime": "mau",
            "todayDate": "2026-06-05",
        })
        self.assertEqual(card["today"]["date"], "2026-06-05")
        self.assertEqual(card["today"]["ganZhi"], "庚戌")

    def test_jeolgi_boundary_gyeongchip(self):
        """절기 경계(경칩 전후)에 월주가 바뀜 — 깨지지 않음 확인."""
        card_early = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "1990-03-01", "birthTime": "o",
        })
        card_late = saju_engine.build_card({
            "gender": "male", "calendar": "solar",
            "birthDate": "1990-03-15", "birthTime": "o",
        })
        self.assertTrue(card_early["pillars"]["month"]["zhi"])
        self.assertTrue(card_late["pillars"]["month"]["zhi"])

    def test_yaja_si_split_option(self):
        """야자시/조자시 분리 옵션: 자시 경계를 실제로 넘는 시각에서 일주 전환.

        진태양시 보정이 시 판정보다 먼저 적용되므로, 보정 후에도 자시(23:00~)에
        들어오도록 longitude=135(보정 0분 근방) + 23:40을 사용한다. 야자시 분리
        (split)에서는 일주가 다음날로 넘어가 standard와 달라야 한다.
        """
        common = {
            "gender": "male", "calendar": "solar",
            "birthDate": "1990-03-15", "birthTimeHm": "23:40",
            "birthLongitude": 135.0,
        }
        std = saju_engine.build_card({**common, "earlyLateZiShi": "standard"})
        split = saju_engine.build_card({**common, "earlyLateZiShi": "split"})
        std_day = std["pillars"]["day"]["gan"] + std["pillars"]["day"]["zhi"]
        split_day = split["pillars"]["day"]["gan"] + split["pillars"]["day"]["zhi"]
        self.assertEqual(std["pillars"]["hour"]["zhi"], "子")
        self.assertNotEqual(std_day, split_day)


class TestShinsalRules(unittest.TestCase):
    """신살 룰셋 단위 테스트."""

    def test_dohwa_present_in_golden(self):
        """골든 케이스: 일지 卯가 도화에 해당(년지 午 기준 火국->卯)."""
        import shinsal_rules
        res = shinsal_rules.compute_shinsal(
            "己", ["午", "卯", "卯", "卯"], ["庚午", "己卯", "己卯", "丁卯"]
        )
        dohwa = [r for r in res if r["name"] == "도화" and r["pos"] is not None]
        self.assertTrue(dohwa, "골든 케이스에 도화가 산출되어야 함")

    def test_all_11_shinsal_keys_present(self):
        """11종 신살이 모두 결과에 키로 존재(부재는 pos=None)."""
        import shinsal_rules
        gan = "甲"
        zhis = ["子", "丑", "寅", "卯"]
        gz = ["甲子", "乙丑", "丙寅", "丁卯"]
        res = shinsal_rules.compute_shinsal(gan, zhis, gz)
        names = {r["name"] for r in res}
        for n in ["도화", "역마", "화개",
                  "천을귀인", "백호", "괴강",
                  "원진", "문창", "양인",
                  "홍염", "귀문관살"]:
            self.assertIn(n, names)


class TestJijanggan(unittest.TestCase):
    """지장간(支藏干) 표준표 단위 테스트 — 모듈 분리 검증."""

    def test_hidden_stems_table(self):
        """표준 지장간(여기->중기->정기 순)."""
        import jijanggan
        self.assertEqual([s["gan"] for s in jijanggan.hidden_stems("子")], ["壬", "癸"])
        self.assertEqual([s["gan"] for s in jijanggan.hidden_stems("丑")], ["癸", "辛", "己"])
        self.assertEqual([s["gan"] for s in jijanggan.hidden_stems("寅")], ["戊", "丙", "甲"])
        self.assertEqual([s["gan"] for s in jijanggan.hidden_stems("午")], ["丙", "己", "丁"])
        self.assertEqual([s["gan"] for s in jijanggan.hidden_stems("亥")], ["戊", "甲", "壬"])

    def test_roles_order(self):
        """역할 라벨: 마지막은 항상 정기, 왕지(子卯酉)는 중기 없음."""
        import jijanggan
        self.assertEqual(jijanggan.hidden_stems("子")[-1]["role"], "정기")
        self.assertEqual([s["role"] for s in jijanggan.hidden_stems("卯")], ["여기", "정기"])
        self.assertEqual([s["role"] for s in jijanggan.hidden_stems("丑")],
                         ["여기", "중기", "정기"])

    def test_jeonggi_matches_main_qi(self):
        """정기(正氣) 오행 = 엔진의 지지 본기(ZHI_MAIN_ELEMENT) — 상위집합 불변식."""
        import jijanggan
        for zhi, main_el in saju_engine.ZHI_MAIN_ELEMENT.items():
            jeong = jijanggan.hidden_stems(zhi)[-1]
            self.assertEqual(jeong["role"], "정기")
            self.assertEqual(jeong["element"], main_el, "%s 정기 오행 불일치" % zhi)

    def test_all_12_branches(self):
        """12지지 전부 2~3 지장간, 정기로 끝남."""
        import jijanggan
        for z in ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]:
            stems = jijanggan.hidden_stems(z)
            self.assertTrue(2 <= len(stems) <= 3, "%s 지장간 개수 이상" % z)
            self.assertEqual(stems[-1]["role"], "정기")


class TestDaewoonDeterminism(unittest.TestCase):
    """대운 current 기준연도 인자화 — 결정론(같은 입력->같은 출력)."""

    def _card(self, **extra):
        base = {"gender": "male", "calendar": "solar",
                "birthDate": "1990-03-15", "birthTime": "mau"}
        base.update(extra)
        return saju_engine.build_card(base)

    def test_reference_year_sets_current(self):
        """referenceYear=2026 -> 현재 대운 壬午(28~37세)."""
        c = self._card(referenceYear=2026)
        cur = c["daewoon"]["current"]
        self.assertIsNotNone(cur)
        self.assertEqual(cur["gan"] + cur["zhi"], "壬午")
        self.assertEqual(c["daewoon"]["currentBasisYear"], 2026)

    def test_reference_year_next(self):
        """referenceYear=2027 -> 다음 대운 癸未(38~47세)."""
        cur = self._card(referenceYear=2027)["daewoon"]["current"]
        self.assertEqual(cur["gan"] + cur["zhi"], "癸未")

    def test_no_reference_year_current_none(self):
        """기준연도 미지정 -> current=None(시스템 시각 비의존, 결정론 보장)."""
        c = self._card()
        self.assertIsNone(c["daewoon"]["current"])
        self.assertIsNone(c["daewoon"]["currentBasisYear"])

    def test_determinism_same_input_same_output(self):
        """같은 referenceYear 두 번 호출 -> daewoon 완전 동일."""
        import json
        a = self._card(referenceYear=2026)["daewoon"]
        b = self._card(referenceYear=2026)["daewoon"]
        self.assertEqual(json.dumps(a, ensure_ascii=False, sort_keys=True),
                         json.dumps(b, ensure_ascii=False, sort_keys=True))

    def test_sewoon_year_backcompat_sets_current(self):
        """하위호환: referenceYear 없이 sewoonYear만 줘도 current 산출(2027->癸未)."""
        cur = self._card(sewoonYear=2027)["daewoon"]["current"]
        self.assertEqual(cur["gan"] + cur["zhi"], "癸未")


if __name__ == "__main__":
    unittest.main(verbosity=2)
