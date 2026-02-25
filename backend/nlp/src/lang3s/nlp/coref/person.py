import re
from dataclasses import dataclass
from typing import List, Optional

# fmt: off
PREFIXES = {
# Basic honorifics
    "mr", "mrs", "ms", "miss", "mx",

    # Formal titles
    "sir", "madam", "dame", "lord", "lady", "master", "mistress",

    # Religious
    "rev", "reverend", "fr", "father", "sr", "sister", "br", "brother",
    "pastor", "priest", "rabbi", "imam", "bishop", "archbishop",
    "cardinal", "pope", "elder",

    # Academic medical
    "dr", "doctor", "prof", "professor",

    # Political governmental
    "pres", "president", "vp", "vice president", "sen", "senator",
    "rep", "representative", "cong", "congressman", "congresswoman",
    "gov", "governor", "lt gov", "lieutenant governor", "mayor",
    "amb", "ambassador", "sec", "secretary", "treasurer", "minister",
    "premier", "pm", "prime minister", "chancellor", "commissioner",

    # Judicial legal
    "judge", "justice", "chief justice", "magistrate", "atty", "attorney",
    "gen atty", "attorney general", "solicitor", "counsel",

    # Military ranks common as prefixes
    "gen", "general", "lt", "lieutenant", "col", "colonel", "maj", "major",
    "capt", "captain", "cmdr", "commander", "adm", "admiral", "sgt", "sergeant",
    "cpl", "corporal", "pvt", "private", "officer", "det", "detective",
    "chief", "trooper",

    # Royalty nobility
    "king", "queen", "prince", "princess", "duke", "duchess", "earl",
    "count", "countess", "baron", "baroness", "emperor", "empress", "sultan",
    "sheikh",

    # Business professional (occasionally prefix like newswire)
    "ceo", "cfo", "cto", "coo", "founder", "chairman", "chairwoman",
    "chair", "director", "coach"
}
# fmt: on

# fmt: off
SUFFIXES = {
    # Generational
    "jr", "sr", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",

    # Academic degrees
    "phd", "md", "do", "dmd", "dds", "dvm", "edd", "dphil",
    "jd", "llb", "llm", "sj d", "mba", "mha", "mph", "msc", "ma", "ms",
    "mfa", "meng", "mpp", "mphil", "ba", "bs", "bsc", "bfa", "bba",
    "beng", "barch",

    # Professional certifications licenses
    "esq", "esquire", "cpa", "cfa", "cfp", "pe", "pte", "rn", "lpn",
    "np", "pa", "pharmd", "od", "au d", "psyd", "dpt", "otd",
    "cissp", "pmp", "csm", "lean", "six sigma",

    # Religious orders honors
    "sj", "op", "ofm", "osb", "sjc",

    # Military honors awards (often seen as suffix strings)
    "ret", "retired", "usn ret", "usa ret", "usaf ret",
    "mc", "vc", "gc", "obe", "mbe", "cbe", "kbe", "gbe",

    # Professional fellowships memberships
    "frs", "facs", "facp", "fache", "fichem e", "fieee", "fasa",

    # Misc honorific academic distinctions
    "hdr", "dr habil", "habil", "cand scient", "cand med"
}
# fmt: on

# fmt: off
NICKNAMES = {
    "abby": "abigail",
    "abe": "abraham",
    "ace": "arthur",
    "alex": "alexander",
    "alfie": "alfred",
    "ally": "allison",
    "amy": "amanda",
    "andy": "andrew",
    "angie": "angela",
    "annie": "anne",
    "art": "arthur",
    "ash": "ashley",
    "barb": "barbara",
    "becky": "rebecca",
    "ben": "benjamin",
    "bern": "bernard",
    "bert": "albert",
    "beth": "elizabeth",
    "betsy": "elizabeth",
    "betty": "elizabeth",
    "bill": "william",
    "billy": "william",
    "bobby": "robert",
    "bob": "robert",
    "brad": "bradley",
    "brian": "bryan",
    "bri": "brian",
    "cal": "calvin",
    "cam": "cameron",
    "cathy": "catherine",
    "cate": "catherine",
    "charlie": "charles",
    "chris": "christopher",
    "chrissy": "christina",
    "cindy": "cynthia",
    "claire": "clarissa",
    "connie": "constance",
    "dan": "daniel",
    "danny": "daniel",
    "dave": "david",
    "davy": "david",
    "deb": "deborah",
    "debbie": "deborah",
    "denny": "dennis",
    "don": "donald",
    "donnie": "donald",
    "dora": "dorothy",
    "dot": "dorothy",
    "dottie": "dorothy",
    "ed": "edward",
    "eddie": "edward",
    "edie": "edith",
    "elaine": "eleanor",
    "ellie": "eleanor",
    "em": "emma",
    "ernie": "ernest",
    "esther": "essie",
    "evie": "eve",
    "fran": "frances",
    "frank": "francis",
    "frankie": "francis",
    "fred": "frederick",
    "freddie": "frederick",
    "gabe": "gabriel",
    "gail": "abigail",
    "gary": "garrett",
    "gene": "eugene",
    "geoff": "geoffrey",
    "georgie": "george",
    "gerry": "gerald",
    "gina": "regina",
    "greg": "gregory",
    "gus": "augustus",
    "hal": "henry",
    "hank": "henry",
    "harry": "henry",
    "helen": "helena",
    "ian": "john",
    "irv": "irving",
    "jack": "john",
    "jackie": "jacqueline",
    "jake": "jacob",
    "jan": "janet",
    "janie": "jane",
    "jay": "jason",
    "jeff": "jeffrey",
    "jen": "jennifer",
    "jenny": "jennifer",
    "jer": "jeremy",
    "jerry": "gerald",
    "jess": "jessica",
    "jim": "james",
    "jimmy": "james",
    "jo": "joanne",
    "joan": "joanna",
    "joe": "joseph",
    "joey": "joseph",
    "johnny": "john",
    "jon": "jonathan",
    "joni": "jonathan",
    "judy": "judith",
    "jules": "julian",
    "julie": "julia",
    "ken": "kenneth",
    "kenny": "kenneth",
    "kim": "kimberly",
    "kathy": "katherine",
    "kate": "katherine",
    "katie": "katherine",
    "kat": "katherine",
    "kay": "katherine",
    "kristy": "kristine",
    "kris": "kristopher",
    "larry": "lawrence",
    "laurie": "laura",
    "leo": "leonard",
    "len": "leonard",
    "lenny": "leonard",
    "liz": "elizabeth",
    "lizzy": "elizabeth",
    "libby": "elizabeth",
    "lisa": "elizabeth",
    "lou": "louis",
    "louie": "louis",
    "lucy": "lucille",
    "maddie": "madeline",
    "maggie": "margaret",
    "mandy": "amanda",
    "marc": "marcus",
    "marge": "margaret",
    "margo": "margaret",
    "marty": "martin",
    "mary": "maria",
    "mat": "matthew",
    "matt": "matthew",
    "meg": "megan",
    "mel": "melanie",
    "mick": "michael",
    "mickey": "michael",
    "mike": "michael",
    "mindy": "melinda",
    "missy": "melissa",
    "mo": "morris",
    "monty": "montgomery",
    "nancy": "anne",
    "nat": "nathaniel",
    "nate": "nathaniel",
    "ned": "edward",
    "nick": "nicholas",
    "nikki": "nicole",
    "norm": "norman",
    "ollie": "oliver",
    "pat": "patrick",
    "patty": "patricia",
    "patti": "patricia",
    "peggy": "margaret",
    "penny": "penelope",
    "pete": "peter",
    "phil": "philip",
    "philly": "philip",
    "polly": "mary",
    "rachel": "rachael",
    "randy": "randall",
    "ray": "raymond",
    "reg": "reginald",
    "rick": "richard",
    "ricky": "richard",
    "rich": "richard",
    "rob": "robert",
    "robbie": "robert",
    "ron": "ronald",
    "ronnie": "ronald",
    "rose": "rosalind",
    "ross": "roscoe",
    "russ": "russell",
    "sam": "samuel",
    "sammie": "samuel",
    "sandy": "alexander",
    "sue": "susan",
    "suzie": "susan",
    "steve": "steven",
    "stevie": "steven",
    "stu": "stuart",
    "ted": "theodore",
    "teddy": "theodore",
    "terry": "terence",
    "tess": "theresa",
    "theo": "theodore",
    "tim": "timothy",
    "timmy": "timothy",
    "tina": "christina",
    "toby": "tobias",
    "tom": "thomas",
    "tommy": "thomas",
    "tony": "anthony",
    "trish": "patricia",
    "val": "valerie",
    "vicky": "victoria",
    "vic": "victor",
    "vin": "vincent",
    "vinnie": "vincent",
    "walt": "walter",
    "wayne": "duane",
    "will": "william",
    "willie": "william",
    "winnie": "winifred",
    "yuri": "george",
    "zack": "zachary",
    "ziggy": "sigmund"
}
# fmt: on


@dataclass
class ParsedName:
    original: str
    normalized: str
    tokens: List[str]
    first: Optional[str]
    middle: List[str]
    last: Optional[str]
    suffix: Optional[str]
    nickname: Optional[str]
    initials: List[str]


def _normalize(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text)  # remove parentheses
    text = re.sub(r"[^\w\s,.-]", " ", text)  # strip weird chars
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_prefix(tokens: List[str]) -> List[str]:
    if tokens and tokens[0].rstrip(".").lower() in PREFIXES:
        return tokens[1:]
    return tokens


def _extract_suffix(tokens: List[str]):
    if tokens and tokens[-1].rstrip(".").lower() in SUFFIXES:
        return tokens[:-1], tokens[-1].rstrip(".").lower()
    return tokens, None


def _detect_initials(tokens: List[str]) -> List[str]:
    initials = []
    for t in tokens:
        if re.fullmatch(r"[A-Z]\.?", t):
            initials.append(t[0])
    return initials


def _canonical_first(first: Optional[str]) -> Optional[str]:
    if not first:
        return None
    return NICKNAMES.get(first.lower(), first.lower())


def parse_person_name(text: str) -> ParsedName:
    original = text
    text = _normalize(text)

    # handle "Last, First Middle"
    if "," in text:
        last, rest = [x.strip() for x in text.split(",", 1)]
        tokens = rest.split() + [last]
    else:
        tokens = text.split()

    tokens = _strip_prefix(tokens)
    tokens, suffix = _extract_suffix(tokens)

    if not tokens:
        return ParsedName(original, text, [], None, [], None, suffix, None, [])

    # assign roles
    first = tokens[0].rstrip(".")
    last = tokens[-1].rstrip(".") if len(tokens) > 1 else None
    middle = [t.rstrip(".") for t in tokens[1:-1]] if len(tokens) > 2 else []

    initials = _detect_initials(tokens)

    nickname = None
    if first.lower() in NICKNAMES:
        nickname = first.lower()
        first = NICKNAMES[first.lower()]

    return ParsedName(
        original=original,
        normalized=text,
        tokens=tokens,
        first=first.lower() if first else None,
        middle=[m.lower() for m in middle],
        last=last.lower() if last else None,
        suffix=suffix,
        nickname=nickname,
        initials=initials,
    )


def surname_match(a: ParsedName, b: ParsedName) -> bool:
    return a.last and b.last and a.last == b.last


def first_match(a: ParsedName, b: ParsedName) -> bool:
    return a.first and b.first and a.first == b.first


def compatible_initials(a: ParsedName, b: ParsedName) -> bool:
    return bool(set(a.initials) & set(b.initials))


def strong_person_conflict(a: ParsedName, b: ParsedName) -> bool:
    # same first but different last
    if a.first and b.first and a.first == b.first and a.last != b.last:
        return True

    # same last but incompatible first (no nickname link)
    if a.last and b.last and a.last == b.last:
        if a.first and b.first and a.first != b.first:
            if _canonical_first(a.first) != _canonical_first(b.first):
                return True

    return False
