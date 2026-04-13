"""
domain_config.py — Single source of truth for all domain definitions.

Every other module imports from here. To add a new domain:
  1. Add its name to SUPPORTED_DOMAINS.
  2. Add its patterns to DOMAIN_PATTERNS.
  3. Add its attribute weights to DOMAIN_ATTRIBUTE_WEIGHTS.
  4. Add its section map to DOMAIN_SECTION_MAPS.
  5. Add its labeling weights to DOMAIN_LABELING_WEIGHTS.
  6. Add its arXiv categories to DOMAIN_ARXIV_CATEGORIES.
  7. No other file needs editing.
"""
from __future__ import annotations

import re
from typing import Dict, List

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
SUPPORTED_DOMAINS: List[str] = [
    "ml",        # Machine Learning / AI (OpenReview)
    "physics",   # High-Energy / Experimental Physics (arXiv)
    "biomed",    # Quantitative Biology / Biomedical (arXiv q-bio)
    "nlp",       # Natural Language Processing (arXiv cs.CL / OpenReview ACL)
    "finance",   # Quantitative Finance (arXiv q-fin)
    "hardware",  # Computer Architecture / Hardware (arXiv cs.AR)
    "math",      # Mathematics (arXiv math)
]

DOMAIN_DISPLAY_NAMES: Dict[str, str] = {
    "ml":       "Machine Learning / AI",
    "physics":  "Physics / HEP",
    "biomed":   "Biomedical / Quantitative Biology",
    "nlp":      "Natural Language Processing",
    "finance":  "Quantitative Finance",
    "hardware": "Computer Architecture / Hardware",
    "math":     "Mathematics",
}

# arXiv category query strings for collection
DOMAIN_ARXIV_CATEGORIES: Dict[str, str] = {
    "physics":  "cat:hep-ex OR cat:physics.ins-det OR cat:hep-ph",
    "biomed":   "cat:q-bio.QM OR cat:q-bio.GN OR cat:q-bio.PE",
    "nlp":      "cat:cs.CL OR cat:cs.IR",
    "finance":  "cat:q-fin.ST OR cat:q-fin.PR OR cat:q-fin.RM",
    "hardware": "cat:cs.AR OR cat:cs.OS OR cat:cs.PF",
    "math":     "cat:math.CO OR cat:math.AT OR cat:math.LO OR cat:math.ST",
    # ml uses OpenReview — no arXiv category needed
}

# The 13 canonical attribute names (fixed across all domains)
ATTRIBUTE_ORDER: List[str] = [
    "code_artifact",
    "data_artifact",
    "availability_statement",
    "execution_instructions",
    "hyperparams_detail",
    "seed_disclosed",
    "compute_detail",
    "software_versions",
    "evaluation_protocol",
    "ablation",
    "baseline_comparison",
    "statistical_rigor",
    "limitations",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def rc(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# ---------------------------------------------------------------------------
# DOMAIN_PATTERNS
# Each domain defines its own regex lists per category.
# Unknown categories fall back to the "universal" set below.
# ---------------------------------------------------------------------------

_UNIVERSAL_PATTERNS: Dict[str, List[re.Pattern]] = {
    # Code
    "code_url": [
        rc(r"github\.com/"),
        rc(r"gitlab\.com/"),
        rc(r"bitbucket\.org/"),
        rc(r"anonymous\.4open\.science"),
        rc(r"codeocean\.com/"),
        rc(r"osf\.io/"),
    ],
    "code_claim": [
        rc(r"\bsource code\b"),
        rc(r"\bcode (?:is|will be|has been)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bimplementation (?:is|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:the )?code\b"),
        rc(r"\bopen[- ]source\b"),
    ],
    "code_future": [
        rc(r"\bcode will be available upon acceptance\b"),
        rc(r"\bcode will be released\b"),
        rc(r"\bcode will be made available\b"),
        rc(r"\bavailable upon acceptance\b"),
    ],
    "code_negative": [
        rc(r"\bno (?:public )?(?:code|implementation|artifact)\b"),
        rc(r"\bwithout (?:code|implementation|artifact)\b"),
        rc(r"\black(?:s|ing)? (?:code|implementation|artifact)\b"),
    ],
    # Data
    "data_url": [
        rc(r"huggingface\.co/"),
        rc(r"zenodo\.org/"),
        rc(r"figshare\.com/"),
        rc(r"osf\.io/"),
        rc(r"kaggle\.com/"),
        rc(r"dataverse\."),
    ],
    "data_claim": [
        rc(r"\bdataset (?:is|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bdata (?:is|are|will be)?\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:the )?(?:dataset|data)\b"),
        rc(r"\bpublicly available (?:benchmark|benchmarks|dataset|datasets|data)\b"),
    ],
    "data_future": [
        rc(r"\bdata will be available upon acceptance\b"),
        rc(r"\bdataset will be released\b"),
        rc(r"\bdata will be released\b"),
    ],
    # Availability
    "availability_confirmed": [
        rc(r"\bartifact(?:s)? (?:are|is)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bcode (?:is|has been)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bdata (?:is|are|has been)\s*(?:available|released|shared|provided)\b"),
        rc(r"\bwe release (?:all )?(?:code|data|models|artifacts)\b"),
        rc(r"github\.com/"),
        rc(r"zenodo\.org/"),
        rc(r"figshare\.com/"),
        rc(r"huggingface\.co/"),
        rc(r"osf\.io/"),
    ],
    "availability_partial": [
        rc(r"\bcode will be available upon acceptance\b"),
        rc(r"\bartifact(?:s)? will be (?:available|released|shared|provided)\b"),
        rc(r"\bsupplementary material\b"),
    ],
    # Execution
    "execution_instruction": [
        rc(r"\bpip install\b"),
        rc(r"\bconda install\b"),
        rc(r"\brequirements\.txt\b"),
        rc(r"\bdocker(?:file)?\b"),
        rc(r"\bto reproduce\b"),
        rc(r"\breproduc(?:e|ing|ibility) package\b"),
        rc(r"\brun the following command\b"),
        rc(r"\bscript(?:s)? (?:are|is)? available\b"),
        rc(r"\btraining script\b"),
        rc(r"\bstep[- ]by[- ]step\b"),
    ],
    # Hyperparams (ML-generic)
    "hyperparams": [
        rc(r"\blearning rate\b"),
        rc(r"\bbatch size\b"),
        rc(r"\bepochs?\b"),
        rc(r"\bweight decay\b"),
        rc(r"\bdropout\b"),
        rc(r"\boptimizer\b"),
        rc(r"\bhyperparameter(?:s)?\b"),
        rc(r"\bwarmup\b"),
    ],
    # Seed
    "seed_strict": [
        rc(r"\brandom seed\b"),
        rc(r"\bseed\s*=\s*\d+\b"),
        rc(r"\bseeded with \d+\b"),
        rc(r"\bwe set (?:the )?seed to \d+\b"),
        rc(r"\brandom_state\s*=\s*\d+\b"),
    ],
    # Compute
    "compute_strong": [
        rc(r"\bNVIDIA\b"),
        rc(r"\bH100\b"),
        rc(r"\bA100\b"),
        rc(r"\bV100\b"),
        rc(r"\bRTX\b"),
        rc(r"\bTPU\b"),
        rc(r"\bGPU(?:s)?\b"),
        rc(r"\btraining time\b"),
        rc(r"\bwall[- ]clock\b"),
        rc(r"\bcompute budget\b"),
    ],
    "compute_partial": [
        rc(r"\bCUDA\b"),
        rc(r"\bcompute\b"),
        rc(r"\bhardware\b"),
    ],
    # Software
    "software_strong": [
        rc(r"\bPyTorch\s*\d+(?:\.\d+)+\b"),
        rc(r"\bTensorFlow\s*\d+(?:\.\d+)+\b"),
        rc(r"\btransformers\s*\d+(?:\.\d+)+\b"),
        rc(r"\bPython\s*\d+(?:\.\d+)+\b"),
        rc(r"\brequirements\.txt\b"),
        rc(r"\bDocker(?:file)?\b"),
    ],
    "software_partial": [
        rc(r"\bPyTorch\b"),
        rc(r"\bTensorFlow\b"),
        rc(r"\bscikit-learn\b"),
        rc(r"\bCUDA\b"),
        rc(r"\bR\s+version\s+\d+\b"),
        rc(r"\bMatlab\b"),
    ],
    # Evaluation
    "benchmarks": [
        rc(r"\bbenchmark(?:s)?\b"),
        rc(r"\btest set\b"),
        rc(r"\bevaluation protocol\b"),
        rc(r"\bvalidation set\b"),
    ],
    "metrics": [
        rc(r"\baccuracy\b"),
        rc(r"\bF1\b"),
        rc(r"\bprecision\b"),
        rc(r"\brecall\b"),
        rc(r"\bRMSE\b"),
        rc(r"\bMAE\b"),
        rc(r"\bAUC\b"),
    ],
    "inference_detail": [
        rc(r"\bgreedy decoding\b"),
        rc(r"\bdeterministic\b"),
    ],
    # Ablation / baselines / stats / limitations
    "ablation": [
        rc(r"\bablation (?:study|studies|experiment|experiments)\b"),
        rc(r"\bwe ablate\b"),
    ],
    "baseline": [
        rc(r"\bbaseline(?:s)?\b"),
        rc(r"\bcompare(?:d)? (?:with|to|against)\b"),
        rc(r"\boutperform(?:s|ed|ing)?\b"),
        rc(r"\bstate[- ]of[- ]the[- ]art\b"),
    ],
    "stat_rigor": [
        rc(r"\bconfidence interval(?:s)?\b"),
        rc(r"\bstandard deviation\b"),
        rc(r"\bstandard error\b"),
        rc(r"\bmultiple runs?\b"),
        rc(r"\bp[- ]value\b"),
        rc(r"\bsignificance\b"),
        rc(r"\bbootstrap\b"),
        rc(r"\bvariance\b"),
    ],
    "limitations": [
        rc(r"\blimitations?\b"),
        rc(r"\bthreats to validity\b"),
        rc(r"\bfuture work\b"),
        rc(r"\bbias\b"),
    ],
}

# Deep-copy universal patterns as ML base, then add ML-specific
_ML_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_ML_PATTERNS["hyperparams"] += [
    rc(r"\bglobal batch size\b"),
    rc(r"\bKL penalty\b"),
    rc(r"\bsampling temperature\b"),
    rc(r"\bnumber of rollouts\b"),
]
_ML_PATTERNS["compute_strong"] += [
    rc(r"\bH200\b"),
    rc(r"\bvLLM\b"),
]
_ML_PATTERNS["software_strong"] += [
    rc(r"\bvLLM\b"),
    rc(r"\bverl\b"),
]
_ML_PATTERNS["benchmarks"] += [
    rc(r"\bMMLU\b"),
    rc(r"\bBIG-Bench\b"),
    rc(r"\bHellaSwag\b"),
    rc(r"\bGSM8K\b"),
    rc(r"\bHumanEval\b"),
]
_ML_PATTERNS["metrics"] += [
    rc(r"\bperplexity\b"),
    rc(r"\bBLEU\b"),
    rc(r"\bRouge\b"),
]

# NLP extends ML with annotation-specific patterns
_NLP_PATTERNS = {k: list(v) for k, v in _ML_PATTERNS.items()}
_NLP_PATTERNS["data_url"] += [
    rc(r"huggingface\.co/datasets/"),
    rc(r"github\.com/.*dataset"),
]
_NLP_PATTERNS["hyperparams"] += [
    rc(r"\bvocabulary size\b"),
    rc(r"\bmax(?:imum)? sequence length\b"),
    rc(r"\battention head(?:s)?\b"),
]
_NLP_PATTERNS["benchmarks"] += [
    rc(r"\bGLUE\b"),
    rc(r"\bSuperGLUE\b"),
    rc(r"\bSQuAD\b"),
    rc(r"\bCoNLL\b"),
    rc(r"\bOntoNotes\b"),
]
_NLP_PATTERNS["annotation_rigor"] = [
    rc(r"\binter[- ]?annotator agreement\b"),
    rc(r"\bCohen.s kappa\b"),
    rc(r"\bIAA\b"),
    rc(r"\bannotation guideline(?:s)?\b"),
    rc(r"\bcrowd[- ]?work(?:ers?)?\b"),
]

# Physics patterns
_PHYSICS_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_PHYSICS_PATTERNS["code_url"] += [
    rc(r"gitlab\.cern\.ch/"),
    rc(r"hepforge\.org/"),
    rc(r"inspire[- ]?hep\.net/"),
]
_PHYSICS_PATTERNS["hyperparams"] = [
    rc(r"\bcut(?:-off|off)?\b"),
    rc(r"\bcross[- ]section\b"),
    rc(r"\benergy threshold\b"),
    rc(r"\bcenter[- ]of[- ]mass energy\b"),
    rc(r"\bcollision energy\b"),
    rc(r"\btrigger\b"),
    rc(r"\bsimulation parameter(?:s)?\b"),
]
_PHYSICS_PATTERNS["compute_strong"] += [
    rc(r"\bCERN\b"),
    rc(r"\bLHC\b"),
    rc(r"\bcomputing cluster\b"),
    rc(r"\bGRID\b"),
    rc(r"\bfarm\b"),
]
_PHYSICS_PATTERNS["software_strong"] = [
    rc(r"\bGeant4\b"),
    rc(r"\bPythia\s*\d+\b"),
    rc(r"\bMadGraph\b"),
    rc(r"\bRoot\s+version\b"),
    rc(r"\bROOT\b"),
    rc(r"\bHerwig\b"),
    rc(r"\bSherpa\b"),
    rc(r"\bFastJet\b"),
]
_PHYSICS_PATTERNS["software_partial"] = [
    rc(r"\bGeant\b"),
    rc(r"\bPythia\b"),
    rc(r"\bROOT\b"),
    rc(r"\bC\+\+\b"),
    rc(r"\bFortran\b"),
]
_PHYSICS_PATTERNS["data_url"] += [
    rc(r"inspire[- ]?hep\.net/"),
    rc(r"hepdata\.net/"),
    rc(r"cern\.ch/"),
]
_PHYSICS_PATTERNS["stat_rigor"] += [
    rc(r"\bsystematic uncertainty\b"),
    rc(r"\bluminosity\b"),
    rc(r"\bbackground estimation\b"),
    rc(r"\bMonte Carlo\b"),
    rc(r"\bCLs?\b"),
    rc(r"\bchi[- ]?square\b"),
    rc(r"\blikelihood ratio\b"),
]
_PHYSICS_PATTERNS["benchmarks"] += [
    rc(r"\bATLAS\b"),
    rc(r"\bCMS\b"),
    rc(r"\bLHCb\b"),
    rc(r"\bALICE\b"),
    rc(r"\bdetector simulation\b"),
]
_PHYSICS_PATTERNS["simulation"] = [
    rc(r"\bMonte Carlo\b"),
    rc(r"\bGeant4\b"),
    rc(r"\bPythia\b"),
    rc(r"\bMadGraph\b"),
    rc(r"\bfast simulation\b"),
    rc(r"\bfull simulation\b"),
    rc(r"\bparton shower\b"),
]

# Biomed patterns
_BIOMED_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_BIOMED_PATTERNS["data_url"] += [
    rc(r"ncbi\.nlm\.nih\.gov/geo/"),
    rc(r"sra\.ncbi\.nlm\.nih\.gov/"),
    rc(r"ebi\.ac\.uk/"),
    rc(r"rcsb\.org/"),
    rc(r"dbgap\b"),
    rc(r"bioproject\b"),
    rc(r"clinicaltrials\.gov/"),
    rc(r"protocols\.io/"),
]
_BIOMED_PATTERNS["biomed_data"] = [
    rc(r"\bGEO accession\b"),
    rc(r"\bSRA accession\b"),
    rc(r"\bdataset.*?deposited\b"),
    rc(r"\bsequence data.*?available\b"),
    rc(r"\bPDB\s+ID\b"),
    rc(r"\bProtein Data Bank\b"),
]
_BIOMED_PATTERNS["biomed_reagents"] = [
    rc(r"\bRRID\b"),
    rc(r"\bcell line authentication\b"),
    rc(r"\bantibody validation\b"),
    rc(r"\bprimary antibod(?:y|ies)\b"),
    rc(r"\batcc\.org\b"),
    rc(r"\bzaagi\.com\b"),
    rc(r"\brepository number\b"),
]
_BIOMED_PATTERNS["biomed_protocol"] = [
    rc(r"\bclinical trial registration\b"),
    rc(r"\bIRB approval\b"),
    rc(r"\bregistered report\b"),
    rc(r"\bCONSORT\b"),
    rc(r"\bPRISMA\b"),
    rc(r"\bMIQE\b"),
    rc(r"\bRECIST\b"),
    rc(r"\bprotocol registration\b"),
]
_BIOMED_PATTERNS["hyperparams"] = [
    rc(r"\bsample size\b"),
    rc(r"\bstatistical power\b"),
    rc(r"\bconfidence level\b"),
    rc(r"\bsignificance level\b"),
    rc(r"\bstudy design\b"),
    rc(r"\binclusion criteria\b"),
    rc(r"\bexclusion criteria\b"),
    rc(r"\bfollowup\b"),
]
_BIOMED_PATTERNS["stat_rigor"] += [
    rc(r"\bsurvival analysis\b"),
    rc(r"\bhazard ratio\b"),
    rc(r"\bodds ratio\b"),
    rc(r"\bKaplan[- ]Meier\b"),
    rc(r"\bWilcoxon\b"),
    rc(r"\bFDR\b"),
    rc(r"\bbonferroni\b"),
    rc(r"\bmultivariate\b"),
]
_BIOMED_PATTERNS["software_strong"] = [
    rc(r"\bBioconductor\b"),
    rc(r"\bR\s+version\s+\d+\.\d+\b"),
    rc(r"\bSPSS\b"),
    rc(r"\bSAS\s+\d+\b"),
    rc(r"\bSTATA\b"),
    rc(r"\bSnakemake\b"),
    rc(r"\bNextflow\b"),
]
_BIOMED_PATTERNS["software_partial"] = [
    rc(r"\bBioconductor\b"),
    rc(r"\bBioPython\b"),
    rc(r"\bR\s+package\b"),
    rc(r"\bSPSS\b"),
    rc(r"\bSAS\b"),
    rc(r"\bSTATA\b"),
    rc(r"\bImageJ\b"),
]
_BIOMED_PATTERNS["benchmarks"] += [
    rc(r"\bROC curve\b"),
    rc(r"\bAUROC\b"),
    rc(r"\bsensitivity\b"),
    rc(r"\bspecificity\b"),
    rc(r"\bcross-validation\b"),
]

# Finance patterns
_FINANCE_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_FINANCE_PATTERNS["data_url"] += [
    rc(r"wrds\.wharton\.upenn\.edu/"),
    rc(r"bloomberg\.com/"),
    rc(r"refinitiv\.com/"),
    rc(r"quandl\.com/"),
    rc(r"fred\.stlouisfed\.org/"),
]
_FINANCE_PATTERNS["finance_data"] = [
    rc(r"\bCRSP\b"),
    rc(r"\bCompustat\b"),
    rc(r"\bBloomberg\b"),
    rc(r"\bRefiNitiv\b"),
    rc(r"\bWRDS\b"),
    rc(r"\bDataStream\b"),
    rc(r"\bthomson reuters\b"),
]
_FINANCE_PATTERNS["hyperparams"] = [
    rc(r"\blookback period\b"),
    rc(r"\brebalancing frequency\b"),
    rc(r"\btransaction cost(?:s)?\b"),
    rc(r"\bwindow size\b"),
    rc(r"\bin[- ]sample\b"),
    rc(r"\bout[- ]of[- ]sample\b"),
    rc(r"\bbacktest(?:ing)?\b"),
]
_FINANCE_PATTERNS["stat_rigor"] += [
    rc(r"\bSharpe ratio\b"),
    rc(r"\bmaximum drawdown\b"),
    rc(r"\bNewey[- ]West\b"),
    rc(r"\bbootstrap\b"),
    rc(r"\bHansen[- ]Jagannathan\b"),
    rc(r"\brobust standard error(?:s)?\b"),
]
_FINANCE_PATTERNS["software_strong"] = [
    rc(r"\bMatlab\s*R\d{4}\b"),
    rc(r"\bStata\s*\d+\b"),
    rc(r"\bPython\s*\d+\.\d+\b"),
    rc(r"\bR\s*\d+\.\d+\b"),
    rc(r"\bEViews\b"),
]
_FINANCE_PATTERNS["software_partial"] = [
    rc(r"\bMatlab\b"),
    rc(r"\bStata\b"),
    rc(r"\bEViews\b"),
    rc(r"\bR\s+package\b"),
    rc(r"\bQuantLib\b"),
]

# Hardware patterns
_HARDWARE_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_HARDWARE_PATTERNS["code_url"] += [
    rc(r"opencores\.org/"),
    rc(r"github\.com/.*(?:rtl|verilog|vhdl|fpga)"),
]
_HARDWARE_PATTERNS["hardware_artifact"] = [
    rc(r"\bVerilog\b"),
    rc(r"\bVHDL\b"),
    rc(r"\bSystemVerilog\b"),
    rc(r"\bFPGA\b"),
    rc(r"\bRTL\b"),
    rc(r"\btestbench\b"),
    rc(r"\bsynthesis report\b"),
]
_HARDWARE_PATTERNS["hyperparams"] = [
    rc(r"\bfrequency\b"),
    rc(r"\bclock cycle(?:s)?\b"),
    rc(r"\blatency\b"),
    rc(r"\bthroughput\b"),
    rc(r"\bfanout\b"),
    rc(r"\btiming constraint(?:s)?\b"),
    rc(r"\bFPGA utilization\b"),
]
_HARDWARE_PATTERNS["compute_strong"] += [
    rc(r"\bXilinx\b"),
    rc(r"\bAltera\b"),
    rc(r"\bIntel FPGA\b"),
    rc(r"\bASIC\b"),
    rc(r"\btape[- ]out\b"),
]
_HARDWARE_PATTERNS["software_strong"] = [
    rc(r"\bVivado\b"),
    rc(r"\bQuartus\b"),
    rc(r"\bSynopsys\b"),
    rc(r"\bCadence\b"),
    rc(r"\bQuesta\b"),
    rc(r"\bModelSim\b"),
]
_HARDWARE_PATTERNS["software_partial"] = [
    rc(r"\bVivado\b"),
    rc(r"\bQuartus\b"),
    rc(r"\bVerilog\b"),
    rc(r"\bVHDL\b"),
    rc(r"\bYosys\b"),
]
_HARDWARE_PATTERNS["benchmarks"] += [
    rc(r"\bCOREMARK\b"),
    rc(r"\bDHRYSTONE\b"),
    rc(r"\bSPEC\b"),
    rc(r"\bMLPerf\b"),
    rc(r"\bpareto[- ]front\b"),
]

# Math patterns
_MATH_PATTERNS = {k: list(v) for k, v in _UNIVERSAL_PATTERNS.items()}
_MATH_PATTERNS["code_url"] += [
    rc(r"coq\.inria\.fr/"),
    rc(r"lean\.mathlib\b"),
]
_MATH_PATTERNS["math_artifact"] = [
    rc(r"\btheorem\s+\d+\b"),
    rc(r"\blemma\s+\d+\b"),
    rc(r"\bproof\s+of\s+theorem\b"),
    rc(r"\bcorollary\b"),
    rc(r"\bformally verified\b"),
    rc(r"\bCoq proof\b"),
    rc(r"\bLean formalization\b"),
    rc(r"\bIsabelle\b"),
]
_MATH_PATTERNS["hyperparams"] = [
    rc(r"\bcomplexity\b"),
    rc(r"\bconvergence rate\b"),
    rc(r"\biteration(?:s)?\b"),
    rc(r"\bdimension\b"),
    rc(r"\bboundary condition(?:s)?\b"),
]
_MATH_PATTERNS["stat_rigor"] += [
    rc(r"\bconvergence proof\b"),
    rc(r"\bexact solution\b"),
    rc(r"\bnumerical stability\b"),
    rc(r"\berror bound\b"),
    rc(r"\btight bound\b"),
]
_MATH_PATTERNS["software_strong"] = [
    rc(r"\bSageMath\b"),
    rc(r"\bMaple\s*\d+\b"),
    rc(r"\bMathematica\s*\d+\b"),
    rc(r"\bGAP\b"),
    rc(r"\bMagma\b"),
    rc(r"\bPARI/GP\b"),
]
_MATH_PATTERNS["software_partial"] = [
    rc(r"\bSageMath\b"),
    rc(r"\bMaple\b"),
    rc(r"\bMathematica\b"),
    rc(r"\bMatlab\b"),
    rc(r"\bnumpy\b"),
    rc(r"\bscipy\b"),
]
_MATH_PATTERNS["benchmarks"] += [
    rc(r"\bcomputational experiment(?:s)?\b"),
    rc(r"\btest instance(?:s)?\b"),
    rc(r"\bbenchmark instance(?:s)?\b"),
]

DOMAIN_PATTERNS: Dict[str, Dict[str, List[re.Pattern]]] = {
    "ml":       _ML_PATTERNS,
    "nlp":      _NLP_PATTERNS,
    "physics":  _PHYSICS_PATTERNS,
    "biomed":   _BIOMED_PATTERNS,
    "finance":  _FINANCE_PATTERNS,
    "hardware": _HARDWARE_PATTERNS,
    "math":     _MATH_PATTERNS,
}


# ---------------------------------------------------------------------------
# DOMAIN_ATTRIBUTE_WEIGHTS
# Must sum to 1.0 for each domain.
# ---------------------------------------------------------------------------
DOMAIN_ATTRIBUTE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "ml": {
        "code_artifact":       0.16,
        "data_artifact":       0.10,
        "availability_statement": 0.05,
        "execution_instructions": 0.10,
        "hyperparams_detail":  0.12,
        "seed_disclosed":      0.08,
        "compute_detail":      0.08,
        "software_versions":   0.08,
        "evaluation_protocol": 0.10,
        "ablation":            0.05,
        "baseline_comparison": 0.04,
        "statistical_rigor":   0.02,
        "limitations":         0.02,
    },
    "nlp": {
        "code_artifact":       0.14,
        "data_artifact":       0.12,
        "availability_statement": 0.06,
        "execution_instructions": 0.10,
        "hyperparams_detail":  0.10,
        "seed_disclosed":      0.07,
        "compute_detail":      0.06,
        "software_versions":   0.07,
        "evaluation_protocol": 0.12,
        "ablation":            0.06,
        "baseline_comparison": 0.06,
        "statistical_rigor":   0.02,
        "limitations":         0.02,
    },
    "physics": {
        "code_artifact":       0.08,
        "data_artifact":       0.12,
        "availability_statement": 0.06,
        "execution_instructions": 0.07,
        "hyperparams_detail":  0.09,
        "seed_disclosed":      0.06,
        "compute_detail":      0.10,
        "software_versions":   0.10,
        "evaluation_protocol": 0.10,
        "ablation":            0.04,
        "baseline_comparison": 0.05,
        "statistical_rigor":   0.09,
        "limitations":         0.04,
    },
    "biomed": {
        "code_artifact":       0.06,
        "data_artifact":       0.15,
        "availability_statement": 0.07,
        "execution_instructions": 0.06,
        "hyperparams_detail":  0.07,
        "seed_disclosed":      0.05,
        "compute_detail":      0.04,
        "software_versions":   0.06,
        "evaluation_protocol": 0.12,
        "ablation":            0.04,
        "baseline_comparison": 0.06,
        "statistical_rigor":   0.14,
        "limitations":         0.08,
    },
    "finance": {
        "code_artifact":       0.10,
        "data_artifact":       0.15,
        "availability_statement": 0.07,
        "execution_instructions": 0.07,
        "hyperparams_detail":  0.10,
        "seed_disclosed":      0.06,
        "compute_detail":      0.04,
        "software_versions":   0.07,
        "evaluation_protocol": 0.10,
        "ablation":            0.04,
        "baseline_comparison": 0.06,
        "statistical_rigor":   0.10,
        "limitations":         0.04,
    },
    "hardware": {
        "code_artifact":       0.14,
        "data_artifact":       0.08,
        "availability_statement": 0.05,
        "execution_instructions": 0.12,
        "hyperparams_detail":  0.12,
        "seed_disclosed":      0.04,
        "compute_detail":      0.12,
        "software_versions":   0.10,
        "evaluation_protocol": 0.10,
        "ablation":            0.04,
        "baseline_comparison": 0.05,
        "statistical_rigor":   0.02,
        "limitations":         0.02,
    },
    "math": {
        "code_artifact":       0.08,
        "data_artifact":       0.06,
        "availability_statement": 0.06,
        "execution_instructions": 0.07,
        "hyperparams_detail":  0.07,
        "seed_disclosed":      0.04,
        "compute_detail":      0.05,
        "software_versions":   0.07,
        "evaluation_protocol": 0.12,
        "ablation":            0.08,
        "baseline_comparison": 0.10,
        "statistical_rigor":   0.14,
        "limitations":         0.06,
    },
}

# Validate all weight sets sum to 1.0
for _dom, _weights in DOMAIN_ATTRIBUTE_WEIGHTS.items():
    assert set(_weights.keys()) == set(ATTRIBUTE_ORDER), (
        f"DOMAIN_ATTRIBUTE_WEIGHTS[{_dom!r}] keys do not match ATTRIBUTE_ORDER"
    )
    _total = sum(_weights.values())
    assert abs(_total - 1.0) < 1e-6, (
        f"DOMAIN_ATTRIBUTE_WEIGHTS[{_dom!r}] sums to {_total:.6f}, not 1.0"
    )


# ---------------------------------------------------------------------------
# DOMAIN_SECTION_MAPS
# Groups of attributes into named sections for the scoring report.
# ---------------------------------------------------------------------------
DOMAIN_SECTION_MAPS: Dict[str, Dict[str, List[str]]] = {
    "ml": {
        "artifacts_and_data": [
            "code_artifact", "data_artifact",
            "availability_statement", "execution_instructions",
        ],
        "implementation_detail": [
            "hyperparams_detail", "seed_disclosed",
            "compute_detail", "software_versions",
        ],
        "evaluation_rigor": [
            "evaluation_protocol", "ablation",
            "baseline_comparison", "statistical_rigor", "limitations",
        ],
    },
    "nlp": {
        "artifacts_and_data": [
            "code_artifact", "data_artifact",
            "availability_statement", "execution_instructions",
        ],
        "implementation_detail": [
            "hyperparams_detail", "seed_disclosed",
            "compute_detail", "software_versions",
        ],
        "evaluation_rigor": [
            "evaluation_protocol", "ablation",
            "baseline_comparison", "statistical_rigor", "limitations",
        ],
    },
    "physics": {
        "data_and_simulation": [
            "data_artifact", "availability_statement",
            "code_artifact", "execution_instructions",
        ],
        "analysis_detail": [
            "hyperparams_detail", "compute_detail",
            "software_versions", "seed_disclosed",
        ],
        "statistical_and_evaluation": [
            "evaluation_protocol", "statistical_rigor",
            "baseline_comparison", "ablation", "limitations",
        ],
    },
    "biomed": {
        "data_and_reagents": [
            "data_artifact", "availability_statement",
            "code_artifact", "execution_instructions",
        ],
        "study_design": [
            "hyperparams_detail", "seed_disclosed",
            "compute_detail", "software_versions",
        ],
        "reporting_rigor": [
            "statistical_rigor", "evaluation_protocol",
            "baseline_comparison", "ablation", "limitations",
        ],
    },
    "finance": {
        "data_and_code": [
            "data_artifact", "code_artifact",
            "availability_statement", "execution_instructions",
        ],
        "methodology": [
            "hyperparams_detail", "seed_disclosed",
            "compute_detail", "software_versions",
        ],
        "empirical_rigor": [
            "statistical_rigor", "evaluation_protocol",
            "baseline_comparison", "ablation", "limitations",
        ],
    },
    "hardware": {
        "design_artifacts": [
            "code_artifact", "availability_statement",
            "execution_instructions", "data_artifact",
        ],
        "implementation": [
            "hyperparams_detail", "compute_detail",
            "software_versions", "seed_disclosed",
        ],
        "evaluation": [
            "evaluation_protocol", "baseline_comparison",
            "ablation", "statistical_rigor", "limitations",
        ],
    },
    "math": {
        "proof_and_code": [
            "code_artifact", "availability_statement",
            "execution_instructions", "data_artifact",
        ],
        "methodology": [
            "hyperparams_detail", "software_versions",
            "compute_detail", "seed_disclosed",
        ],
        "rigor_and_evaluation": [
            "statistical_rigor", "evaluation_protocol",
            "baseline_comparison", "ablation", "limitations",
        ],
    },
}

# Validate section maps cover ATTRIBUTE_ORDER exactly once
for _dom, _smap in DOMAIN_SECTION_MAPS.items():
    _attrs = [a for attrs in _smap.values() for a in attrs]
    assert sorted(_attrs) == sorted(ATTRIBUTE_ORDER), (
        f"DOMAIN_SECTION_MAPS[{_dom!r}] does not cover ATTRIBUTE_ORDER exactly: "
        f"got {sorted(_attrs)}"
    )


# ---------------------------------------------------------------------------
# DOMAIN_LABELING_WEIGHTS
# Used by build_labeled_dataset_auto.py for weighted_positive_support().
# These are raw importance weights (not normalized) used for YES/NO decisions.
# ---------------------------------------------------------------------------
DOMAIN_LABELING_WEIGHTS: Dict[str, Dict[str, float]] = {
    "ml": {
        "code_artifact": 2.2, "data_artifact": 1.4,
        "availability_statement": 0.9, "execution_instructions": 1.8,
        "hyperparams_detail": 1.7, "seed_disclosed": 1.1,
        "compute_detail": 1.1, "software_versions": 1.3,
        "evaluation_protocol": 1.7, "ablation": 0.9,
        "baseline_comparison": 0.8, "statistical_rigor": 0.6, "limitations": 0.4,
    },
    "nlp": {
        "code_artifact": 2.0, "data_artifact": 1.8,
        "availability_statement": 1.0, "execution_instructions": 1.6,
        "hyperparams_detail": 1.5, "seed_disclosed": 1.1,
        "compute_detail": 0.9, "software_versions": 1.1,
        "evaluation_protocol": 1.8, "ablation": 1.0,
        "baseline_comparison": 1.2, "statistical_rigor": 0.6, "limitations": 0.4,
    },
    "physics": {
        "code_artifact": 1.2, "data_artifact": 2.0,
        "availability_statement": 1.0, "execution_instructions": 1.3,
        "hyperparams_detail": 1.4, "seed_disclosed": 0.8,
        "compute_detail": 1.5, "software_versions": 1.6,
        "evaluation_protocol": 1.6, "ablation": 0.6,
        "baseline_comparison": 0.8, "statistical_rigor": 1.8, "limitations": 0.7,
    },
    "biomed": {
        "code_artifact": 1.0, "data_artifact": 2.5,
        "availability_statement": 1.2, "execution_instructions": 1.0,
        "hyperparams_detail": 1.1, "seed_disclosed": 0.7,
        "compute_detail": 0.6, "software_versions": 0.9,
        "evaluation_protocol": 1.8, "ablation": 0.6,
        "baseline_comparison": 0.9, "statistical_rigor": 2.2, "limitations": 1.2,
    },
    "finance": {
        "code_artifact": 1.5, "data_artifact": 2.2,
        "availability_statement": 1.0, "execution_instructions": 1.3,
        "hyperparams_detail": 1.5, "seed_disclosed": 0.9,
        "compute_detail": 0.7, "software_versions": 1.1,
        "evaluation_protocol": 1.6, "ablation": 0.7,
        "baseline_comparison": 1.0, "statistical_rigor": 1.8, "limitations": 0.7,
    },
    "hardware": {
        "code_artifact": 2.0, "data_artifact": 1.2,
        "availability_statement": 0.9, "execution_instructions": 1.9,
        "hyperparams_detail": 1.8, "seed_disclosed": 0.6,
        "compute_detail": 1.7, "software_versions": 1.6,
        "evaluation_protocol": 1.6, "ablation": 0.7,
        "baseline_comparison": 0.9, "statistical_rigor": 0.4, "limitations": 0.4,
    },
    "math": {
        "code_artifact": 1.2, "data_artifact": 0.8,
        "availability_statement": 0.8, "execution_instructions": 1.1,
        "hyperparams_detail": 1.0, "seed_disclosed": 0.5,
        "compute_detail": 0.8, "software_versions": 1.0,
        "evaluation_protocol": 1.7, "ablation": 1.3,
        "baseline_comparison": 1.5, "statistical_rigor": 2.0, "limitations": 1.0,
    },
}


# ---------------------------------------------------------------------------
# LLM prompt templates for auto-labeling (llm_auto_label.py)
# ---------------------------------------------------------------------------
DOMAIN_LLM_PROMPTS: Dict[str, str] = {
    "ml": """You are an expert ML reproducibility reviewer. Score this ML paper's reproducibility from 0 to 100.
Consider: (1) Code availability (GitHub/similar), (2) Dataset availability, (3) Hyperparameter reporting,
(4) Hardware/compute details, (5) Random seed disclosure, (6) Software versions, (7) Evaluation protocol clarity.
100 = perfectly reproducible (code+data released, all hyperparams reported, full environment specified).
0 = impossible to reproduce (no code, no data, key details missing).
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "physics": """You are an expert physics reproducibility reviewer. Score this physics paper's reproducibility from 0 to 100.
Consider: (1) Data availability (HEPData, CERN opendata), (2) Simulation code (Geant4/Pythia config),
(3) Statistical methodology completeness, (4) Software versions (ROOT, Geant4), 
(5) Analysis parameters, (6) Systematic uncertainty reporting.
100 = fully reproducible. 0 = not reproducible.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "biomed": """You are an expert biomedical reproducibility reviewer. Score this paper's reproducibility from 0 to 100.
Consider: (1) Data deposition (GEO/SRA accession numbers), (2) Reagent identification (RRIDs),
(3) Protocol registration (ClinicalTrials.gov), (4) Statistical reporting completeness,
(5) Sample size justification, (6) Code/analysis script availability, (7) Limitations section.
100 = fully reproducible. 0 = not reproducible.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "nlp": """You are an expert NLP reproducibility reviewer. Score this NLP paper's reproducibility from 0 to 100.
Consider: (1) Code release (GitHub), (2) Dataset release or benchmark specification,
(3) Model hyperparameters, (4) Annotation guidelines and IAA, (5) Evaluation protocol,
(6) Random seed disclosure, (7) Pre-processing steps.
100 = fully reproducible. 0 = not reproducible.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "finance": """You are an expert quantitative finance reproducibility reviewer. Score this paper from 0 to 100.
Consider: (1) Data source specification (CRSP, Compustat, Bloomberg), (2) Code availability,
(3) Backtest parameters and methodology, (4) Statistical robustness checks, (5) Transaction cost assumptions,
(6) In-sample/out-of-sample split specification.
100 = fully reproducible. 0 = not reproducible.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "hardware": """You are an expert hardware/architecture reproducibility reviewer. Score this paper from 0 to 100.
Consider: (1) RTL/HDL code availability (Verilog/VHDL), (2) Synthesis tool and version,
(3) FPGA/ASIC platform specification, (4) Timing constraints and utilization reports,
(5) Benchmark specifications, (6) Simulation scripts.
100 = fully reproducible. 0 = not reproducible.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",

    "math": """You are an expert mathematics reproducibility reviewer. Score this paper from 0 to 100.
Consider: (1) Formal proof completeness, (2) Computational experiment code availability,
(3) Software/CAS specification (Sage, Mathematica), (4) Proof verification tool (Coq, Lean, Isabelle),
(5) Counterexample or example reproducibility, (6) Clarity of theorem statements.
100 = fully verifiable. 0 = not verifiable.
Return ONLY a JSON object: {"score": <integer 0-100>, "label": "<YES|NO>", "reason": "<one sentence>"}
YES means reproducible (score >= 60), NO means not (score < 60).""",
}


# ---------------------------------------------------------------------------
# Convenience getters
# ---------------------------------------------------------------------------
def get_domain_patterns(domain: str) -> Dict[str, List[re.Pattern]]:
    if domain not in DOMAIN_PATTERNS:
        raise ValueError(
            f"Unknown domain {domain!r}. Supported: {SUPPORTED_DOMAINS}"
        )
    return DOMAIN_PATTERNS[domain]


def get_domain_weights(domain: str) -> Dict[str, float]:
    if domain not in DOMAIN_ATTRIBUTE_WEIGHTS:
        raise ValueError(f"Unknown domain {domain!r}")
    return DOMAIN_ATTRIBUTE_WEIGHTS[domain]


def get_domain_labeling_weights(domain: str) -> Dict[str, float]:
    if domain not in DOMAIN_LABELING_WEIGHTS:
        raise ValueError(f"Unknown domain {domain!r}")
    return DOMAIN_LABELING_WEIGHTS[domain]


def get_domain_section_map(domain: str) -> Dict[str, List[str]]:
    if domain not in DOMAIN_SECTION_MAPS:
        raise ValueError(f"Unknown domain {domain!r}")
    return DOMAIN_SECTION_MAPS[domain]


def get_domain_llm_prompt(domain: str) -> str:
    return DOMAIN_LLM_PROMPTS.get(domain, DOMAIN_LLM_PROMPTS["ml"])


def validate_domain(domain: str) -> str:
    """Return domain if valid, raise ValueError otherwise."""
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError(
            f"Unknown domain {domain!r}. Supported domains: {SUPPORTED_DOMAINS}"
        )
    return domain
