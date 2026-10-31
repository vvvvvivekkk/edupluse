"""Initial learning content: topics, intervention types and learning resources."""

TOPICS = ["Loops", "Functions", "Arrays & Strings", "Recursion", "Object-Oriented Basics"]

INTERVENTION_TYPES = [
    ("targeted_material", "Targeted Learning Material",
     "Concept explanations, notes and reading/video material for the topic where support is needed."),
    ("targeted_practice", "Targeted Practice Questions",
     "Topic-specific practice questions to reinforce understanding."),
    ("study_plan", "Personalized Study Plan",
     "A structured day-by-day plan to improve study consistency and complete outstanding work."),
    ("faculty_support", "Faculty Support",
     "Consultation or follow-up review with a faculty member."),
]

MATERIAL = {
    "Loops": ("https://docs.python.org/3/tutorial/controlflow.html#for-statements",
              "Understand for/while loops, range(), break and continue."),
    "Functions": ("https://docs.python.org/3/tutorial/controlflow.html#defining-functions",
                  "Define functions, use parameters, return values and default arguments."),
    "Arrays & Strings": ("https://docs.python.org/3/tutorial/introduction.html#lists",
                         "Index, slice and iterate over lists and strings."),
    "Recursion": ("https://en.wikibooks.org/wiki/Python_Programming/Functions#Recursion",
                  "Write recursive functions with a correct base case."),
    "Object-Oriented Basics": ("https://docs.python.org/3/tutorial/classes.html",
                               "Define classes, create objects and use methods and attributes."),
}

PRACTICE = {
    "Loops": [
        {"q": "How many times does `for i in range(2, 10, 3): print(i)` print?", "options": ["2", "3", "4", "8"], "answer": 1},
        {"q": "What does `break` do inside a loop?", "options": ["Skips to the next iteration", "Exits the loop immediately", "Restarts the loop", "Raises an error"], "answer": 1},
        {"q": "What is printed?  `s=0` then `for i in range(4): s+=i` then `print(s)`", "options": ["4", "6", "10", "3"], "answer": 1},
        {"q": "Which loop is best when the number of iterations is not known in advance?", "options": ["for over range()", "while", "list comprehension", "None of these"], "answer": 1},
        {"q": "What does `continue` do?", "options": ["Ends the program", "Exits the loop", "Skips the rest of the current iteration", "Pauses execution"], "answer": 2},
    ],
    "Functions": [
        {"q": "What does a function return if it has no return statement?", "options": ["0", "None", "False", "An error"], "answer": 1},
        {"q": "Given `def f(a, b=2): return a*b`, what is `f(3)`?", "options": ["3", "5", "6", "Error"], "answer": 2},
        {"q": "Which keyword defines a function in Python?", "options": ["func", "function", "def", "lambda only"], "answer": 2},
        {"q": "Variables created inside a function are by default...", "options": ["global", "local to the function", "shared with all functions", "constants"], "answer": 1},
        {"q": "What is `len` in `len([1,2,3])`?", "options": ["A keyword", "A built-in function", "A variable", "A class attribute"], "answer": 1},
    ],
    "Arrays & Strings": [
        {"q": "For `a=[10,20,30,40]`, what is `a[-1]`?", "options": ["10", "40", "Error", "30"], "answer": 1},
        {"q": "What is `'python'[1:4]`?", "options": ["pyt", "yth", "ytho", "pyth"], "answer": 1},
        {"q": "Which method adds an item to the end of a list?", "options": ["add()", "push()", "append()", "insert_end()"], "answer": 2},
        {"q": "Strings in Python are...", "options": ["mutable", "immutable", "lists", "always numeric"], "answer": 1},
        {"q": "What is `len('hi there')`?", "options": ["7", "8", "2", "6"], "answer": 1},
    ],
    "Recursion": [
        {"q": "What is essential to stop a recursive function?", "options": ["A loop", "A base case", "A global variable", "A return of None"], "answer": 1},
        {"q": "`def f(n): return 1 if n==0 else n*f(n-1)`. What is f(4)?", "options": ["10", "24", "4", "16"], "answer": 1},
        {"q": "What happens with recursion that never reaches a base case in Python?", "options": ["Runs forever silently", "RecursionError", "Returns 0", "Compiles to a loop"], "answer": 1},
        {"q": "`def g(n): return 0 if n==0 else n+g(n-1)`. What is g(3)?", "options": ["3", "6", "9", "0"], "answer": 1},
        {"q": "Each recursive call uses...", "options": ["no memory", "a new stack frame", "the same variables", "a new process"], "answer": 1},
    ],
    "Object-Oriented Basics": [
        {"q": "What is `self` in a method definition?", "options": ["A keyword for the class", "The instance the method is called on", "A global variable", "Optional decoration"], "answer": 1},
        {"q": "Which method runs when an object is created?", "options": ["__new_object__", "__init__", "__start__", "create()"], "answer": 1},
        {"q": "An object is...", "options": ["A function", "An instance of a class", "A module", "A loop"], "answer": 1},
        {"q": "`class Dog(Animal):` means Dog...", "options": ["contains an Animal", "inherits from Animal", "is unrelated", "replaces Animal"], "answer": 1},
        {"q": "Attributes defined with `self.x = 1` in `__init__` belong to...", "options": ["the class only", "each instance", "the module", "no one"], "answer": 1},
    ],
}


def study_plan(topic):
    return {"days": [
        {"day": 1, "task": f"Re-read your notes on {topic} and list three things you find unclear (45 min)."},
        {"day": 2, "task": f"Work through the {topic} reading material and rewrite each example yourself (60 min)."},
        {"day": 3, "task": "Finish any pending assignment work; submit even if incomplete (60 min)."},
        {"day": 4, "task": f"Solve 5 practice problems on {topic}; note which ones you got wrong (45 min)."},
        {"day": 5, "task": "Attend every lecture/lab this week and review the day's code the same evening (30 min)."},
        {"day": 6, "task": f"Re-attempt the problems you got wrong on day 4 without looking at solutions (45 min)."},
        {"day": 7, "task": "Short self-review: what improved, what still needs help? Then take the follow-up assessment."},
    ]}


def _shuffle_answers(bank: dict, seed: int = 31) -> dict:
    """Deterministically shuffle option order so the correct answer is not always in the same position."""
    import random
    rng = random.Random(seed)
    out = {}
    for topic, qs in bank.items():
        new = []
        for q in qs:
            order = list(range(len(q["options"])))
            rng.shuffle(order)
            new.append({"q": q["q"], "options": [q["options"][i] for i in order], "answer": order.index(q["answer"])})
        out[topic] = new
    return out


PRACTICE = _shuffle_answers(PRACTICE)
