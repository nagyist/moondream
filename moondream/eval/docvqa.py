import argparse
import editdistance
from datasets import load_dataset
from tqdm import tqdm
import torch

from ..torch.config import MoondreamConfig
from ..torch.moondream import MoondreamModel
from ..torch.weights import load_weights_into_model

SUFFIX = " The answer should be a short text span taken verbatim from the document."


def get_anls(s1, s2):
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()
    iou = 1 - editdistance.eval(s1, s2) / max(len(s1), len(s2))
    anls = iou if iou >= 0.5 else 0.0
    return anls


def eval_docvqa(model, debug=False):
    docvqa_val = load_dataset("vikhyatk/docvqa-val", split="validation")

    scores = []
    results = []

    for row in tqdm(docvqa_val, disable=debug, desc="DocVQA"):
        image = row["image"]
        encoded_image = model.encode_image(image)

        result = []
        for qa in row["qa"]:
            question = qa["question"]
            answers = qa["answers"]
            prompt = question + SUFFIX

            model_answer = model.query(encoded_image, prompt)["answer"]
            anls = max(get_anls(model_answer, gt) for gt in answers)
            scores.append(anls)
            result.append(
                {
                    "question": question,
                    "ground_truth": answers,
                    "model_answer": model_answer,
                    "anls": anls,
                }
            )

            if debug:
                print(f"Question: {question}")
                print(f"Ground Truth: {answers}")
                print(f"Model Answer: {model_answer}")
                print(f"ANLS: {anls}")
                print(f"Current Average ANLS: {sum(scores) / len(scores):.4f}")
                print("---------")
        results.append(result)

    return {
        "anls": sum(scores) / len(scores),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if torch.cuda.is_available():
        torch.set_default_device("cuda")
    elif torch.backends.mps.is_available():
        torch.set_default_device("mps")

    config = MoondreamConfig()
    model = MoondreamModel(config)
    load_weights_into_model(args.model, model)
    model.compile()

    result = eval_docvqa(model, args.debug)

    print(f"ANLS: {result['anls']:.4f}")
