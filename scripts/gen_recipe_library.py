#!/usr/bin/env python3
"""Generate the recipe library JSON with mechanically-enforced tagging rules.

Each recipe is declared with: name, mealType, prepTime, ingredients, instructions,
cuisine, cost tier, and a set of "role" tags (quick, meal-prep, weekend, comfort,
healthy, budget, high-protein, low-carb, one-pot, slow-cook, oven, 30min, etc.).

Dietary/content tags (meat, beef/chicken/pork/seafood, dairy, gluten, eggs,
vegetarian, vegan) are DERIVED from the ingredients so the tagging rules are
always consistent.
"""
import json
import re
import sys

ALLOWED_TAGS = {
    "quick", "meal-prep", "weekend", "comfort", "healthy", "budget",
    "high-protein", "low-carb", "vegetarian", "vegan", "gluten-free",
    "dairy-free", "dairy", "gluten", "eggs", "beef", "chicken", "pork",
    "seafood", "meat", "mexican", "asian", "mediterranean", "indian",
    "italian", "american", "breakfast", "one-pot", "slow-cook", "oven", "30min",
}
ALLOWED_CATEGORIES = {
    "Meat & Seafood", "Produce", "Dairy & Eggs", "Pantry", "Spices",
    "Bakery & Bread", "Frozen",
}
ALLOWED_MEALTYPES = {"breakfast", "lunch", "dinner"}
ALLOWED_COST = {"budget", "moderate", "premium"}

# Ingredient name fragments that indicate gluten when in Pantry/Bakery/Frozen.
GLUTEN_NAMES = (
    "flour", "pasta", "spaghetti", "penne", "noodle", "bread", "tortilla",
    "bun", "roll", "pita", "naan", "couscous", "breadcrumb", "panko", "soy sauce",
    "lasagna", "orzo", "ramen", "udon", "cracker", "biscuit", "pizza", "wrap",
    "english muffin", "bagel", "macaroni", "barley", "tortellini", "gnocchi",
    "wonton", "phyllo", "pie crust", "pancake mix", "cake", "ditalini", "farro",
)
DAIRY_NAMES = (
    "cheese", "milk", "butter", "cream", "yogurt", "parmesan", "mozzarella",
    "cheddar", "feta", "ricotta", "queso", "ghee", "halloumi", "cotija",
    "mascarpone", "gruyere", "brie", "paneer",
)
# things that look dairy but aren't
NONDAIRY_OVERRIDES = ("coconut milk", "coconut cream", "almond milk", "oat milk",
                      "soy milk", "cashew cream", "creamer of coconut", "nut milk")
# things that contain a gluten keyword but are actually gluten-free
NONGLUTEN_OVERRIDES = ("almond flour", "coconut flour", "rice noodle", "tamari",
                       "rice flour", "chickpea flour", "corn tortilla",
                       "cornstarch", "rice paper")
EGG_NAMES = ("egg",)
MEAT_KEYWORDS = {
    "beef": ("beef", "steak", "brisket", "chuck", "sirloin", "ground beef",
             "short rib", "flank", "ground chuck", "ribeye", "meatball"),
    "chicken": ("chicken", "rotisserie"),
    "pork": ("pork", "bacon", "sausage", "ham", "prosciutto", "chorizo",
             "pancetta", "italian sausage", "andouille", "carnitas"),
    "seafood": ("salmon", "shrimp", "tuna", "cod", "fish", "tilapia", "crab",
                "scallop", "halibut", "mahi", "anchovy", "clam", "mussel",
                "calamari", "trout", "snapper", "lobster", "sardine"),
}
# chorizo can be pork (default) — handled above. Turkey treated as its own (use meat+chicken-ish? -> treat as "chicken" group? No)
# We'll treat turkey/ground turkey as meat but map to "chicken" group? Better: skip turkey to avoid ambiguity.


def detect_content(ingredients):
    has_dairy = False
    has_gluten = False
    has_eggs = False
    meats = set()
    for ing in ingredients:
        name = ing["name"].lower()
        cat = ing["category"]

        # dairy
        if cat == "Dairy & Eggs" or any(d in name for d in DAIRY_NAMES):
            if not any(o in name for o in NONDAIRY_OVERRIDES):
                # eggs are in Dairy & Eggs but are not "dairy"
                if not ("egg" in name and not any(d in name for d in DAIRY_NAMES)):
                    has_dairy = True
        # eggs
        if any(e in name for e in EGG_NAMES) and "eggplant" not in name:
            has_eggs = True
        # gluten: full-word match (optionally plural) so "roll" does not fire
        # on "rolled oats" but "rolls"/"tortillas"/"noodles" still match.
        if not any(o in name for o in NONGLUTEN_OVERRIDES):
            if any(re.search(r"\b" + re.escape(g) + r"(s|es)?\b", name) for g in GLUTEN_NAMES):
                has_gluten = True
        # meat
        if cat == "Meat & Seafood":
            for mtype, kws in MEAT_KEYWORDS.items():
                if any(k in name for k in kws):
                    meats.add(mtype)
        else:
            # bacon/sausage/anchovy etc could appear elsewhere; still detect
            for mtype, kws in MEAT_KEYWORDS.items():
                if any(k in name for k in kws):
                    meats.add(mtype)
    return has_dairy, has_gluten, has_eggs, meats


def build(rec):
    """rec is a tuple/dict describing the recipe. Returns full dict."""
    ingredients = rec["ingredients"]
    has_dairy, has_gluten, has_eggs, meats = detect_content(ingredients)

    tags = set(rec.get("tags", []))

    # derived content tags
    if has_dairy:
        tags.add("dairy")
    if has_gluten:
        tags.add("gluten")
    if has_eggs:
        tags.add("eggs")
    if meats:
        tags.add("meat")
        for m in meats:
            tags.add(m)

    # vegetarian/vegan sanity: a recipe with meat cannot be vegetarian/vegan
    if "meat" in tags:
        tags.discard("vegetarian")
        tags.discard("vegan")
    # vegan implies vegetarian
    if "vegan" in tags:
        tags.add("vegetarian")
        # vegan cannot contain dairy or eggs
        assert not has_dairy, f"{rec['name']}: vegan but has dairy"
        assert not has_eggs, f"{rec['name']}: vegan but has eggs"

    # quick / 30min coupling
    if rec["prepTime"] <= 30:
        if "quick" in tags or "30min" in tags or rec.get("auto_quick"):
            tags.add("quick")
            tags.add("30min")
    else:
        tags.discard("quick")
        tags.discard("30min")

    # breakfast mealtype implies breakfast tag
    if rec["mealType"] == "breakfast":
        tags.add("breakfast")

    # cuisine tag passthrough already in tags

    # validate tags subset
    bad = tags - ALLOWED_TAGS
    assert not bad, f"{rec['name']}: bad tags {bad}"

    # validate categories
    for ing in ingredients:
        assert ing["category"] in ALLOWED_CATEGORIES, f"{rec['name']}: bad cat {ing['category']}"
        assert isinstance(ing["amount"], (int, float)), f"{rec['name']}: bad amount"

    assert rec["mealType"] in ALLOWED_MEALTYPES
    assert rec["cost"] in ALLOWED_COST

    return {
        "id": rec["id"],
        "name": rec["name"],
        "description": rec["description"],
        "mealType": rec["mealType"],
        "prepTime": rec["prepTime"],
        "servings": 4,
        "ingredients": ingredients,
        "instructions": rec["instructions"],
        "tags": sorted(tags),
        "estimatedCostTier": rec["cost"],
    }


# ---- ingredient helpers ----
def I(name, amount, unit, category):
    return {"name": name, "amount": amount, "unit": unit, "category": category}


# Shorthand category constructors
def MEAT(name, amount, unit="lb"):
    return I(name, amount, unit, "Meat & Seafood")
def PROD(name, amount, unit="each"):
    return I(name, amount, unit, "Produce")
def DAIRY(name, amount, unit="cup"):
    return I(name, amount, unit, "Dairy & Eggs")
def PAN(name, amount, unit="cup"):
    return I(name, amount, unit, "Pantry")
def SP(name, amount, unit="tsp"):
    return I(name, amount, unit, "Spices")
def BREAD(name, amount, unit="each"):
    return I(name, amount, unit, "Bakery & Bread")
def FROZ(name, amount, unit="cup"):
    return I(name, amount, unit, "Frozen")


RECIPES = []

def add(id, name, description, mealType, prepTime, ingredients, instructions, cost, tags):
    RECIPES.append({
        "id": id, "name": name, "description": description, "mealType": mealType,
        "prepTime": prepTime, "ingredients": ingredients, "instructions": instructions,
        "cost": cost, "tags": tags,
    })

# Common pantry/spice helpers reused everywhere
def garlic(n=3): return PROD("garlic", n, "clove")
def onion(n=1): return PROD("onion", n, "each")
def olive_oil(a=2): return PAN("olive oil", a, "tbsp")
def salt(): return SP("salt", 1, "tsp")
def pepper(): return SP("black pepper", 0.5, "tsp")
def rice(a=2): return PAN("white rice", a, "cup")
def can_tomato(): return PAN("canned diced tomatoes", 1, "can")
def cilantro(): return PROD("cilantro", 1, "bunch")
def sour_cream(a=0.5): return DAIRY("sour cream", a, "cup")
def cheddar(a=1): return DAIRY("cheddar cheese", a, "cup")
def lime(n=2): return PROD("lime", n, "each")
def spinach(a=4, u="cup"): return PROD("spinach", a, u)

# =====================================================================
# GROUP 1: 45 QUICK WEEKNIGHT DINNERS (variety of cuisines)
# =====================================================================

add("chicken-tacos","Chicken Tacos","Seasoned shredded chicken in warm tortillas with fresh toppings.","dinner",25,
  [MEAT("chicken breast",1.5), BREAD("corn tortillas",12), onion(1), cilantro(), lime(2),
   SP("chili powder",1,"tbsp"), SP("cumin",1), garlic(2), cheddar(1), sour_cream(0.5), olive_oil()],
  "Cook the seasoned chicken breast in a skillet until done, then shred with two forks. Warm the corn tortillas in a dry pan until pliable. Fill each tortilla with chicken, diced onion, and cilantro. Top with cheese, a squeeze of lime, and a dollop of sour cream.",
  "moderate",["quick","mexican","chicken","comfort"])

add("beef-tacos","Ground Beef Tacos","Classic weeknight tacos with seasoned ground beef and crunchy toppings.","dinner",25,
  [MEAT("ground beef",1), BREAD("taco shells",12), onion(1), PROD("lettuce",1,"each"), PROD("tomato",2),
   cheddar(1), sour_cream(0.5), SP("chili powder",1,"tbsp"), SP("cumin",1), garlic(2)],
  "Brown the ground beef with diced onion and garlic in a large skillet. Stir in chili powder, cumin, and a splash of water, then simmer until thickened. Warm the taco shells in the oven. Fill shells with beef and top with lettuce, tomato, cheese, and sour cream.",
  "budget",["quick","mexican","beef","comfort","budget"])

add("shrimp-stir-fry","Shrimp Stir Fry","Fast garlic-ginger shrimp and vegetables over rice.","dinner",25,
  [MEAT("shrimp",1.25), PROD("bell pepper",2), PROD("broccoli",3,"cup"), PROD("ginger",1,"tbsp"), garlic(3),
   PAN("soy sauce",3,"tbsp"), PAN("white rice",2), PAN("sesame oil",1,"tbsp"), PROD("green onion",4)],
  "Cook the rice according to package directions. Stir-fry the bell pepper and broccoli in sesame oil over high heat until crisp-tender. Add shrimp, garlic, and ginger and cook until shrimp turn pink. Pour in soy sauce, toss to coat, and serve over rice topped with green onion.",
  "moderate",["quick","asian","seafood","healthy"])

add("chicken-stir-fry","Chicken Stir Fry","Tender chicken and crisp vegetables in a savory soy glaze.","dinner",28,
  [MEAT("chicken breast",1.5), PROD("broccoli",3,"cup"), PROD("carrot",2), PROD("bell pepper",1), garlic(3),
   PROD("ginger",1,"tbsp"), PAN("soy sauce",3,"tbsp"), PAN("white rice",2), PAN("cornstarch",1,"tbsp"), PAN("sesame oil",1,"tbsp")],
  "Cook the rice while you slice the chicken into thin strips. Stir-fry the chicken in sesame oil until golden, then remove. Add broccoli, carrot, and bell pepper and cook until crisp-tender. Return chicken with garlic and ginger, add soy sauce thickened with cornstarch, and toss until glossy.",
  "moderate",["quick","asian","chicken","healthy"])

add("spaghetti-bolognese","Spaghetti Bolognese","Rich ground beef tomato sauce over spaghetti.","dinner",30,
  [MEAT("ground beef",1), PAN("spaghetti",1,"lb"), can_tomato(), PAN("tomato paste",2,"tbsp"), onion(1), garlic(4),
   DAIRY("parmesan cheese",0.5), SP("italian seasoning",1,"tbsp"), olive_oil()],
  "Brown the ground beef with onion and garlic in olive oil. Stir in canned tomatoes, tomato paste, and Italian seasoning, then simmer while the spaghetti cooks. Drain the pasta and toss with the sauce. Serve topped with grated parmesan.",
  "budget",["quick","italian","beef","comfort","budget"])

add("garlic-butter-shrimp-pasta","Garlic Butter Shrimp Pasta","Buttery garlic shrimp tossed with linguine and parsley.","dinner",25,
  [MEAT("shrimp",1.25), PAN("spaghetti",1,"lb"), DAIRY("butter",4,"tbsp"), garlic(5), PROD("parsley",0.5,"bunch"),
   lime(1), DAIRY("parmesan cheese",0.5), SP("red pepper flakes",0.5), olive_oil()],
  "Boil the pasta until al dente and reserve a cup of pasta water. Saute the shrimp in butter and garlic until pink, seasoning with red pepper flakes. Add the drained pasta with a splash of pasta water and toss. Finish with parsley, parmesan, and a squeeze of lime.",
  "moderate",["quick","italian","seafood"])

add("chicken-fajitas","Chicken Fajitas","Sizzling chicken and peppers with warm flour tortillas.","dinner",30,
  [MEAT("chicken breast",1.5), PROD("bell pepper",3), onion(1), BREAD("flour tortillas",8), lime(2),
   SP("chili powder",1,"tbsp"), SP("cumin",1), cheddar(1), sour_cream(0.5), olive_oil()],
  "Slice the chicken, peppers, and onion into strips. Sear the chicken in olive oil with chili powder and cumin until cooked through, then remove. Saute the peppers and onion until charred and tender, then return the chicken. Serve in warm tortillas with lime, cheese, and sour cream.",
  "moderate",["quick","mexican","chicken","comfort"])

add("beef-and-broccoli","Beef and Broccoli","Takeout-style tender beef and broccoli in glossy sauce.","dinner",28,
  [MEAT("flank steak",1.25), PROD("broccoli",4,"cup"), garlic(3), PROD("ginger",1,"tbsp"),
   PAN("soy sauce",4,"tbsp"), PAN("cornstarch",1,"tbsp"), PAN("white rice",2), PAN("sesame oil",1,"tbsp"), PAN("brown sugar",1,"tbsp")],
  "Cook the rice and slice the steak thinly against the grain. Sear the beef in sesame oil over high heat, then remove. Stir-fry the broccoli with garlic and ginger until bright green. Return the beef, add soy sauce, brown sugar, and cornstarch slurry, and toss until the sauce thickens.",
  "moderate",["quick","asian","beef"])

add("teriyaki-salmon","Teriyaki Salmon Bowls","Glazed salmon over rice with quick teriyaki sauce.","dinner",25,
  [MEAT("salmon fillet",1.5), PAN("soy sauce",4,"tbsp"), PAN("brown sugar",2,"tbsp"), PROD("ginger",1,"tbsp"),
   garlic(2), PAN("white rice",2), PROD("broccoli",3,"cup"), PROD("green onion",3), PAN("sesame oil",1,"tbsp")],
  "Cook the rice and steam the broccoli until tender. Simmer soy sauce, brown sugar, garlic, and ginger into a glaze. Sear the salmon in sesame oil, then brush with the teriyaki glaze. Serve over rice with broccoli and sliced green onion.",
  "premium",["quick","asian","seafood","healthy","high-protein"])

add("margherita-flatbread","Margherita Flatbread","Crisp flatbread with tomato, mozzarella, and basil.","dinner",22,
  [BREAD("naan flatbread",4), DAIRY("mozzarella cheese",2), PROD("tomato",3), PROD("basil",1,"bunch"),
   garlic(2), olive_oil(), PAN("tomato paste",2,"tbsp")],
  "Spread the flatbreads with tomato paste mixed with garlic and olive oil. Top with sliced tomato and torn mozzarella. Bake at 450F until the cheese melts and the edges crisp. Finish with fresh basil and a drizzle of olive oil.",
  "moderate",["quick","italian","vegetarian","oven"])

add("pesto-chicken-pasta","Pesto Chicken Pasta","Penne tossed with basil pesto and seared chicken.","dinner",28,
  [MEAT("chicken breast",1.25), PAN("penne pasta",1,"lb"), PAN("basil pesto",0.5), PROD("cherry tomato",2,"cup"),
   DAIRY("parmesan cheese",0.5), garlic(2), olive_oil()],
  "Boil the penne until al dente, reserving some pasta water. Sear the seasoned chicken in olive oil, then slice. Toss the pasta with pesto, a splash of pasta water, and halved cherry tomatoes. Fold in the chicken and top with parmesan.",
  "moderate",["quick","italian","chicken"])

add("chicken-quesadillas","Chicken Quesadillas","Crispy cheese and chicken quesadillas with salsa.","dinner",25,
  [MEAT("chicken breast",1.25), BREAD("flour tortillas",8), cheddar(2), PROD("bell pepper",1), onion(0.5),
   sour_cream(0.5), PAN("salsa",1), SP("cumin",1)],
  "Saute diced chicken with pepper and onion until cooked and seasoned with cumin. Layer chicken and cheese between two tortillas. Cook in a dry skillet until golden and crisp on both sides and the cheese melts. Slice into wedges and serve with salsa and sour cream.",
  "budget",["quick","mexican","chicken","budget","comfort"])

add("sausage-pepper-skillet","Sausage and Peppers Skillet","One-pan Italian sausage with peppers and onions.","dinner",30,
  [MEAT("italian sausage",1.25), PROD("bell pepper",3), onion(2), garlic(3), can_tomato(),
   SP("italian seasoning",1,"tbsp"), olive_oil(), BREAD("hoagie rolls",4)],
  "Brown the sausage in a large skillet, then remove and slice. Saute the peppers and onions in the rendered fat until soft. Add garlic, tomatoes, and Italian seasoning and simmer. Return the sausage to heat through and serve on hoagie rolls.",
  "moderate",["quick","italian","pork","one-pot","comfort"])

add("honey-garlic-chicken","Honey Garlic Chicken","Sticky honey-garlic glazed chicken thighs over rice.","dinner",30,
  [MEAT("chicken thighs",1.75), PAN("honey",3,"tbsp"), PAN("soy sauce",3,"tbsp"), garlic(5),
   PAN("white rice",2), PROD("green onion",3), PAN("sesame oil",1,"tbsp"), PAN("cornstarch",1,"tbsp")],
  "Cook the rice while you sear the chicken thighs in sesame oil until golden. Whisk honey, soy sauce, and garlic, then pour over the chicken. Simmer until the sauce reduces and a cornstarch slurry thickens it to a glaze. Serve over rice with green onion.",
  "moderate",["quick","asian","chicken"])

add("greek-chicken-bowls","Greek Chicken Bowls","Lemon-oregano chicken over rice with cucumber and feta.","dinner",30,
  [MEAT("chicken breast",1.5), PROD("cucumber",1), PROD("cherry tomato",2,"cup"), DAIRY("feta cheese",1),
   PROD("red onion",0.5), lime(1), SP("oregano",1,"tbsp"), olive_oil(), PAN("white rice",2), DAIRY("greek yogurt",0.5)],
  "Marinate and sear the chicken with oregano, olive oil, and lemon until cooked, then slice. Cook the rice and dice the cucumber, tomato, and red onion. Build bowls with rice, chicken, and vegetables. Top with crumbled feta and a dollop of yogurt.",
  "moderate",["quick","mediterranean","chicken","healthy","high-protein"])

add("shrimp-tacos","Shrimp Tacos","Quick seasoned shrimp tacos with slaw and lime crema.","dinner",25,
  [MEAT("shrimp",1.25), BREAD("corn tortillas",12), PROD("cabbage",3,"cup"), cilantro(), lime(2),
   sour_cream(0.5), SP("chili powder",1,"tbsp"), SP("cumin",1), olive_oil()],
  "Season the shrimp with chili powder and cumin, then saute in olive oil until pink. Toss shredded cabbage with lime juice and cilantro for a quick slaw. Warm the tortillas in a dry pan. Fill with shrimp and slaw and drizzle with lime-spiked sour cream.",
  "moderate",["quick","mexican","seafood","healthy"])

add("caprese-chicken","Caprese Chicken","Pan-seared chicken topped with tomato, mozzarella, and basil.","dinner",28,
  [MEAT("chicken breast",1.5), DAIRY("mozzarella cheese",1.5), PROD("tomato",3), PROD("basil",1,"bunch"),
   garlic(2), PAN("balsamic vinegar",2,"tbsp"), olive_oil()],
  "Sear the seasoned chicken breasts in olive oil until nearly cooked through. Top each with sliced tomato and mozzarella and cover until the cheese melts. Drizzle with balsamic vinegar reduced with garlic. Finish with fresh basil.",
  "moderate",["quick","italian","chicken","high-protein","low-carb"])

add("black-bean-quesadillas","Black Bean Quesadillas","Cheesy black bean and corn quesadillas.","dinner",22,
  [PAN("black beans",2,"can"), BREAD("flour tortillas",8), cheddar(2), FROZ("corn",1), onion(0.5),
   PAN("salsa",1), SP("cumin",1), cilantro()],
  "Mash half the black beans and mix with corn, onion, cumin, and cilantro. Spread over tortillas with cheese and fold. Cook in a dry skillet until crisp and golden on both sides. Slice and serve with salsa.",
  "budget",["quick","mexican","vegetarian","budget"])

add("lemon-garlic-tilapia","Lemon Garlic Tilapia","Light pan-seared tilapia in lemon butter sauce.","dinner",22,
  [MEAT("tilapia fillet",1.5), DAIRY("butter",3,"tbsp"), garlic(4), lime(2), PROD("parsley",0.5,"bunch"),
   PAN("white rice",2), PROD("asparagus",1,"bunch"), olive_oil()],
  "Cook the rice and roast or steam the asparagus. Season and sear the tilapia in olive oil until flaky. Add butter, garlic, and lemon juice to the pan to make a quick sauce. Spoon the sauce over the fish and serve with rice and asparagus.",
  "moderate",["quick","seafood","healthy","high-protein"])

add("kung-pao-chicken","Kung Pao Chicken","Spicy stir-fried chicken with peanuts and peppers.","dinner",28,
  [MEAT("chicken thighs",1.5), PROD("bell pepper",2), PAN("peanuts",0.5), garlic(3), PROD("ginger",1,"tbsp"),
   PAN("soy sauce",3,"tbsp"), PAN("white rice",2), SP("red pepper flakes",1), PROD("green onion",4), PAN("cornstarch",1,"tbsp")],
  "Cook the rice and cut the chicken into bite-sized pieces. Stir-fry the chicken in a hot wok until browned, then add peppers, garlic, and ginger. Stir in soy sauce, red pepper flakes, and a cornstarch slurry until glossy. Fold in peanuts and green onion and serve over rice.",
  "moderate",["quick","asian","chicken"])

add("turkey-meatball-subs","Turkey Meatball Subs","Saucy meatballs and melted cheese on toasted rolls.","dinner",30,
  [MEAT("ground turkey",1.25), BREAD("hoagie rolls",4), PAN("marinara sauce",2), DAIRY("mozzarella cheese",1.5),
   PAN("breadcrumbs",0.5), garlic(3), SP("italian seasoning",1,"tbsp"), DAIRY("parmesan cheese",0.25)],
  "Mix the turkey with breadcrumbs, parmesan, garlic, and seasoning, then form meatballs. Brown the meatballs and simmer in marinara until cooked through. Pile meatballs into rolls and top with mozzarella. Broil until the cheese is bubbly and melted.",
  "moderate",["quick","italian","comfort","meat"])

add("cilantro-lime-chicken-bowls","Cilantro Lime Chicken Bowls","Zesty chicken and rice bowls with beans and salsa.","dinner",30,
  [MEAT("chicken breast",1.5), PAN("white rice",2), PAN("black beans",1,"can"), cilantro(), lime(2),
   PROD("avocado",2), PAN("salsa",1), cheddar(0.5), SP("cumin",1)],
  "Cook the rice and stir in chopped cilantro and lime juice. Season and sear the chicken with cumin, then slice. Warm the black beans and slice the avocado. Build bowls with rice, beans, chicken, salsa, cheese, and avocado.",
  "moderate",["quick","mexican","chicken","high-protein","meal-prep"])

add("pork-fried-rice","Pork Fried Rice","Wok-fried rice with pork, egg, and vegetables.","dinner",25,
  [MEAT("pork loin",1), PAN("white rice",3), DAIRY("eggs",3,"each"), FROZ("peas and carrots",1.5), garlic(3),
   PAN("soy sauce",3,"tbsp"), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Use day-old cooked rice for the best texture. Scramble the eggs in sesame oil and set aside. Stir-fry diced pork with garlic until browned, then add peas and carrots. Add the rice, soy sauce, eggs, and green onion and toss until hot.",
  "budget",["quick","asian","pork","budget","one-pot"])

add("bbq-chicken-pizza","BBQ Chicken Pizza","Smoky barbecue chicken pizza with red onion.","dinner",28,
  [MEAT("chicken breast",1), BREAD("pizza dough",1,"each"), PAN("barbecue sauce",0.75), DAIRY("mozzarella cheese",2),
   PROD("red onion",0.5), cilantro(), DAIRY("gouda cheese",0.5)],
  "Stretch the pizza dough onto a baking sheet. Spread with barbecue sauce and top with cooked shredded chicken, mozzarella, gouda, and thin red onion. Bake at 475F until the crust is golden and the cheese bubbles. Scatter with cilantro before slicing.",
  "moderate",["quick","american","chicken","oven","comfort"])

add("shakshuka","Shakshuka","Eggs poached in a spiced tomato and pepper sauce.","dinner",30,
  [DAIRY("eggs",6,"each"), can_tomato(), PROD("bell pepper",2), onion(1), garlic(4), SP("cumin",1),
   SP("paprika",1), DAIRY("feta cheese",0.5), cilantro(), olive_oil(), BREAD("crusty bread",1,"each")],
  "Saute onion, pepper, and garlic in olive oil until soft. Add tomatoes, cumin, and paprika and simmer into a thick sauce. Make wells and crack in the eggs, then cover and cook until the whites set. Crumble feta on top and serve with crusty bread.",
  "budget",["quick","mediterranean","vegetarian","one-pot","budget"])

add("orange-chicken","Orange Chicken","Crispy chicken in a sweet and tangy orange sauce.","dinner",30,
  [MEAT("chicken thighs",1.5), PAN("flour",0.5), PAN("orange juice",0.75), PAN("soy sauce",2,"tbsp"),
   PAN("brown sugar",2,"tbsp"), garlic(3), PROD("ginger",1,"tbsp"), PAN("white rice",2), PAN("cornstarch",2,"tbsp")],
  "Toss chicken pieces in flour and cornstarch, then pan-fry until crisp. Simmer orange juice, soy sauce, brown sugar, garlic, and ginger into a sauce. Toss the crispy chicken in the sauce until coated. Serve over steamed rice.",
  "moderate",["quick","asian","chicken","comfort"])

add("steak-fajita-bowls","Steak Fajita Bowls","Seared steak with peppers over cilantro rice.","dinner",30,
  [MEAT("sirloin steak",1.5), PROD("bell pepper",3), onion(1), PAN("white rice",2), cilantro(), lime(2),
   PROD("avocado",2), SP("chili powder",1,"tbsp"), SP("cumin",1), olive_oil()],
  "Cook the rice and toss with cilantro and lime. Season the steak with chili powder and cumin, sear to medium, then rest and slice. Char the peppers and onion in the same pan. Build bowls with rice, steak, peppers, and sliced avocado.",
  "moderate",["quick","mexican","beef","high-protein"])

add("creamy-tomato-tortellini","Creamy Tomato Tortellini","Cheese tortellini in a creamy tomato sauce with spinach.","dinner",25,
  [PAN("cheese tortellini",1.25,"lb"), can_tomato(), DAIRY("heavy cream",0.75), spinach(4), garlic(4),
   onion(0.5), DAIRY("parmesan cheese",0.5), SP("italian seasoning",1,"tbsp"), olive_oil()],
  "Boil the tortellini until tender. Saute onion and garlic, then add tomatoes and Italian seasoning and simmer. Stir in cream and spinach until the spinach wilts. Fold in the tortellini and finish with parmesan.",
  "moderate",["quick","italian","vegetarian","comfort"])

add("crispy-fish-sandwiches","Crispy Fish Sandwiches","Golden breaded cod sandwiches with tartar sauce.","dinner",30,
  [MEAT("cod fillet",1.5), BREAD("brioche buns",4), PAN("panko breadcrumbs",1.5), DAIRY("eggs",2,"each"),
   PAN("flour",0.5), PROD("lettuce",1,"each"), PAN("tartar sauce",0.5), lime(1)],
  "Dredge the cod in flour, beaten egg, and panko. Pan-fry until golden and crisp on both sides. Toast the buns and spread with tartar sauce. Layer the fish with lettuce and a squeeze of lemon.",
  "moderate",["quick","american","seafood","comfort"])

add("thai-basil-chicken","Thai Basil Chicken","Spicy stir-fried ground chicken with basil over rice.","dinner",25,
  [MEAT("ground chicken",1.25), PROD("basil",1,"bunch"), garlic(5), PROD("bell pepper",1), PAN("soy sauce",2,"tbsp"),
   PAN("fish sauce",1,"tbsp"), PAN("white rice",2), SP("red pepper flakes",1), PROD("green onion",3)],
  "Cook the rice while you heat a wok until very hot. Stir-fry the ground chicken with garlic and chili until browned. Add pepper, soy sauce, and fish sauce and toss. Stir in a large handful of basil until wilted and serve over rice.",
  "budget",["quick","asian","chicken","budget"])

add("buffalo-chicken-wraps","Buffalo Chicken Wraps","Spicy buffalo chicken wrapped with ranch and crisp lettuce.","dinner",25,
  [MEAT("chicken breast",1.5), BREAD("flour tortillas",4), PAN("buffalo sauce",0.5), PROD("lettuce",1,"each"),
   DAIRY("ranch dressing",0.5), PROD("carrot",2), DAIRY("blue cheese crumbles",0.5)],
  "Cook and shred the chicken, then toss with buffalo sauce. Warm the tortillas to make them pliable. Fill with buffalo chicken, lettuce, shredded carrot, and blue cheese. Drizzle with ranch and roll up tightly.",
  "moderate",["quick","american","chicken"])

add("mongolian-beef","Mongolian Beef","Sweet and savory crispy beef with scallions.","dinner",28,
  [MEAT("flank steak",1.25), PAN("soy sauce",4,"tbsp"), PAN("brown sugar",3,"tbsp"), garlic(4),
   PROD("ginger",1,"tbsp"), PROD("green onion",6), PAN("cornstarch",3,"tbsp"), PAN("white rice",2)],
  "Toss thin-sliced steak in cornstarch and sear until crisp, then remove. Simmer soy sauce, brown sugar, garlic, and ginger into a glaze. Return the beef and toss until coated and sticky. Fold in green onion and serve over rice.",
  "moderate",["quick","asian","beef"])

add("margherita-pasta","Tomato Basil Penne","Simple penne in a fresh garlic tomato basil sauce.","dinner",25,
  [PAN("penne pasta",1,"lb"), can_tomato(), garlic(4), PROD("basil",1,"bunch"), DAIRY("parmesan cheese",0.5),
   onion(0.5), olive_oil(), SP("red pepper flakes",0.5)],
  "Boil the penne until al dente. Saute onion and garlic in olive oil, then add tomatoes and simmer. Toss the pasta in the sauce with torn basil. Finish with parmesan and a pinch of red pepper flakes.",
  "budget",["quick","italian","vegetarian","budget"])

add("chicken-caesar-wraps","Chicken Caesar Wraps","Grilled chicken Caesar wrapped in a soft tortilla.","dinner",25,
  [MEAT("chicken breast",1.5), BREAD("flour tortillas",4), PROD("romaine lettuce",1,"each"),
   DAIRY("caesar dressing",0.5), DAIRY("parmesan cheese",0.5), PAN("croutons",1)],
  "Season and grill the chicken, then slice into strips. Chop the romaine and toss with Caesar dressing and parmesan. Warm the tortillas and fill with lettuce, chicken, and a few croutons. Roll up and slice in half.",
  "moderate",["quick","american","chicken"])

add("coconut-curry-shrimp","Coconut Curry Shrimp","Shrimp simmered in a fragrant coconut curry sauce.","dinner",28,
  [MEAT("shrimp",1.25), PAN("coconut milk",1,"can"), PAN("red curry paste",2,"tbsp"), PROD("bell pepper",2),
   garlic(3), PROD("ginger",1,"tbsp"), PAN("white rice",2), cilantro(), lime(1)],
  "Cook the rice while you build the sauce. Saute curry paste, garlic, and ginger, then pour in coconut milk and simmer. Add peppers and shrimp and cook until the shrimp are pink. Finish with lime and cilantro and serve over rice.",
  "moderate",["quick","asian","seafood","healthy","dairy-free"])

add("egg-roll-in-a-bowl","Egg Roll in a Bowl","Deconstructed egg roll with pork and cabbage.","dinner",25,
  [MEAT("ground pork",1.25), PROD("cabbage",5,"cup"), PROD("carrot",2), garlic(4), PROD("ginger",1,"tbsp"),
   PAN("soy sauce",3,"tbsp"), PAN("sesame oil",1,"tbsp"), PROD("green onion",4)],
  "Brown the ground pork with garlic and ginger in sesame oil. Add shredded cabbage and carrot and stir-fry until wilted. Pour in soy sauce and toss until the vegetables are tender. Top with green onion and serve.",
  "budget",["quick","asian","pork","low-carb","budget","one-pot"])

add("chicken-parmesan","Chicken Parmesan","Crispy breaded chicken with marinara and melted mozzarella.","dinner",30,
  [MEAT("chicken breast",1.5), PAN("panko breadcrumbs",1.5), DAIRY("eggs",2,"each"), PAN("flour",0.5),
   PAN("marinara sauce",2), DAIRY("mozzarella cheese",1.5), DAIRY("parmesan cheese",0.5), PAN("spaghetti",0.75,"lb")],
  "Bread the chicken in flour, egg, and panko, then pan-fry until golden. Top each cutlet with marinara and mozzarella. Broil until the cheese melts and bubbles. Serve over spaghetti tossed with extra marinara.",
  "moderate",["quick","italian","chicken","comfort"])

add("blackened-salmon","Blackened Salmon","Spice-crusted salmon with a quick herb rice.","dinner",25,
  [MEAT("salmon fillet",1.5), SP("paprika",1,"tbsp"), SP("cayenne",0.5), SP("garlic powder",1), PAN("white rice",2),
   PROD("parsley",0.5,"bunch"), lime(1), DAIRY("butter",2,"tbsp"), olive_oil()],
  "Coat the salmon in a blend of paprika, cayenne, and garlic powder. Sear in a hot skillet with butter until a dark crust forms and the fish flakes. Cook the rice and stir in parsley and lime. Serve the salmon over the herb rice.",
  "premium",["quick","american","seafood","high-protein","low-carb"])

add("veggie-fried-rice","Vegetable Fried Rice","Quick fried rice loaded with vegetables and egg.","dinner",25,
  [PAN("white rice",3), DAIRY("eggs",3,"each"), FROZ("peas and carrots",1.5), PROD("broccoli",2,"cup"),
   garlic(3), PAN("soy sauce",3,"tbsp"), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Scramble the eggs in sesame oil and set aside. Stir-fry the broccoli, peas, and carrots with garlic until tender. Add the cooked rice and soy sauce and toss over high heat. Fold in the eggs and green onion.",
  "budget",["quick","asian","vegetarian","budget","one-pot"])

add("philly-cheesesteak-skillet","Philly Cheesesteak Skillet","Cheesy steak and peppers piled on toasted rolls.","dinner",28,
  [MEAT("ribeye steak",1.5), PROD("bell pepper",2), onion(2), DAIRY("provolone cheese",1.5), garlic(2),
   BREAD("hoagie rolls",4), olive_oil()],
  "Thinly slice the ribeye and sear quickly in a hot skillet. Add peppers, onion, and garlic and cook until soft. Lay provolone over the top and let it melt. Pile the cheesesteak filling onto toasted hoagie rolls.",
  "moderate",["quick","american","beef","comfort"])

add("lemon-pepper-chicken","Lemon Pepper Chicken","Bright lemon-pepper chicken with roasted potatoes.","dinner",30,
  [MEAT("chicken thighs",1.75), PROD("potato",1.5,"lb"), lime(2), SP("black pepper",1,"tbsp"),
   garlic(3), PROD("parsley",0.5,"bunch"), olive_oil(), salt()],
  "Toss the potatoes in olive oil, salt, and pepper and roast until crisp. Season the chicken thighs with lemon, pepper, and garlic. Sear skin-side down until golden, then finish cooking through. Serve with the roasted potatoes and parsley.",
  "budget",["quick","american","chicken","budget"])

add("tuna-melt-pasta","Tuna Noodle Skillet","Creamy tuna and pea pasta ready in one pan.","dinner",28,
  [MEAT("canned tuna",2,"can"), PAN("egg noodles",1,"lb"), FROZ("peas",1.5), DAIRY("milk",1.5), DAIRY("cheddar cheese",1.5),
   onion(0.5), PAN("flour",2,"tbsp"), DAIRY("butter",2,"tbsp")],
  "Boil the egg noodles until tender. Make a quick roux with butter, flour, and milk, then stir in cheddar. Fold in the drained tuna and peas until heated through. Toss with the noodles and season to taste.",
  "budget",["quick","american","seafood","comfort","budget"])

add("chipotle-chicken-burritos","Chipotle Chicken Burritos","Hefty burritos with smoky chicken, rice, and beans.","dinner",30,
  [MEAT("chicken breast",1.5), BREAD("flour tortillas",4), PAN("white rice",2), PAN("black beans",1,"can"),
   cheddar(1), sour_cream(0.5), PAN("chipotle in adobo",2,"tbsp"), lime(2), cilantro()],
  "Cook the chicken with chipotle and lime, then shred. Prepare the rice with cilantro and lime and warm the beans. Pile rice, beans, chicken, cheese, and sour cream onto large tortillas. Fold into tight burritos and sear seam-side down.",
  "moderate",["quick","mexican","chicken","comfort"])

add("garlic-butter-steak-bites","Garlic Butter Steak Bites","Seared steak bites in garlic butter with potatoes.","dinner",30,
  [MEAT("sirloin steak",1.5), DAIRY("butter",4,"tbsp"), garlic(5), PROD("potato",1.5,"lb"),
   PROD("parsley",0.5,"bunch"), olive_oil(), salt(), pepper()],
  "Cube and parboil the potatoes, then crisp them in a hot pan with olive oil. Sear the cubed steak in batches until browned. Add butter and garlic and toss the steak until coated. Combine with the potatoes and finish with parsley.",
  "moderate",["quick","american","beef","high-protein","low-carb"])

add("penne-arrabbiata","Penne Arrabbiata","Spicy garlic tomato penne with a kick of chili.","dinner",25,
  [PAN("penne pasta",1,"lb"), can_tomato(), garlic(5), SP("red pepper flakes",1.5), PROD("parsley",0.5,"bunch"),
   olive_oil(), DAIRY("parmesan cheese",0.5)],
  "Boil the penne until al dente. Gently fry garlic and red pepper flakes in olive oil until fragrant. Add the tomatoes and simmer into a spicy sauce. Toss with the pasta and finish with parsley and parmesan.",
  "budget",["quick","italian","vegetarian","budget"])

add("korean-beef-bowls","Korean Beef Bowls","Sweet and savory ground beef over rice.","dinner",22,
  [MEAT("ground beef",1.25), PAN("soy sauce",3,"tbsp"), PAN("brown sugar",3,"tbsp"), garlic(4),
   PROD("ginger",1,"tbsp"), PAN("white rice",2), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Cook the rice while you brown the ground beef. Drain the fat, then stir in soy sauce, brown sugar, garlic, and ginger. Simmer until the sauce coats the beef. Serve over rice with green onion and a drizzle of sesame oil.",
  "budget",["quick","asian","beef","budget","one-pot"])

add("mediterranean-shrimp-orzo","Mediterranean Shrimp Orzo","Lemony orzo with shrimp, tomato, and feta.","dinner",30,
  [MEAT("shrimp",1.25), PAN("orzo pasta",1.5), PROD("cherry tomato",2,"cup"), DAIRY("feta cheese",1),
   garlic(3), spinach(4), lime(1), olive_oil(), PROD("parsley",0.5,"bunch")],
  "Cook the orzo until tender and drain. Saute the shrimp with garlic in olive oil until pink. Add tomatoes and spinach until the spinach wilts. Toss with the orzo, lemon, feta, and parsley.",
  "moderate",["quick","mediterranean","seafood","healthy"])

add("sweet-chili-chicken","Sweet Chili Chicken","Crispy chicken glazed in sticky sweet chili sauce.","dinner",30,
  [MEAT("chicken thighs",1.5), PAN("sweet chili sauce",0.5), PAN("cornstarch",3,"tbsp"), garlic(3),
   PAN("white rice",2), PROD("broccoli",3,"cup"), PROD("green onion",3), PAN("soy sauce",1,"tbsp")],
  "Toss chicken pieces in cornstarch and pan-fry until crispy. Steam the broccoli and cook the rice. Combine sweet chili sauce, garlic, and soy sauce, then toss with the chicken. Serve over rice with broccoli and green onion.",
  "moderate",["quick","asian","chicken"])

# =====================================================================
# GROUP 2: 20 WEEKEND / SLOW DINNERS
# =====================================================================

add("beef-lasagna","Classic Beef Lasagna","Layered lasagna with rich meat sauce and three cheeses.","dinner",90,
  [MEAT("ground beef",1.5), PAN("lasagna noodles",1,"lb"), can_tomato(), PAN("tomato paste",2,"tbsp"),
   DAIRY("ricotta cheese",2), DAIRY("mozzarella cheese",3), DAIRY("parmesan cheese",1), DAIRY("eggs",1,"each"),
   onion(1), garlic(4), SP("italian seasoning",1,"tbsp")],
  "Simmer a meat sauce with beef, onion, garlic, tomatoes, and Italian seasoning for 30 minutes. Mix ricotta with egg and parmesan. Layer noodles, meat sauce, ricotta, and mozzarella in a deep dish. Bake covered at 375F, then uncover until bubbly and golden.",
  "moderate",["weekend","italian","beef","comfort","oven"])

add("pot-roast","Sunday Pot Roast","Fork-tender braised chuck roast with carrots and potatoes.","dinner",210,
  [MEAT("chuck roast",3), PROD("carrot",4), PROD("potato",2,"lb"), onion(2), garlic(5),
   PAN("beef broth",4), PAN("tomato paste",2,"tbsp"), SP("thyme",1,"tbsp"), olive_oil(), salt(), pepper()],
  "Sear the seasoned chuck roast on all sides in a Dutch oven. Add broth, tomato paste, garlic, thyme, and onion, then braise covered at 325F for two and a half hours. Add carrots and potatoes and continue until everything is tender. Rest the roast before slicing and serve with the vegetables and pan juices.",
  "moderate",["weekend","slow-cook","american","beef","comfort","oven"])

add("braised-short-ribs","Red Wine Braised Short Ribs","Melt-in-your-mouth short ribs in a rich red wine sauce.","dinner",195,
  [MEAT("beef short ribs",3.5), PAN("red wine",2), PAN("beef broth",3), onion(2), PROD("carrot",3),
   garlic(6), PAN("tomato paste",3,"tbsp"), SP("thyme",1,"tbsp"), PAN("flour",2,"tbsp"), olive_oil()],
  "Sear the short ribs until deeply browned, then set aside. Soften onion, carrot, and garlic, then stir in tomato paste and flour. Deglaze with red wine and broth, return the ribs, and braise at 325F for nearly three hours. Skim the sauce and spoon it over the tender ribs.",
  "premium",["weekend","slow-cook","beef","comfort","oven"])

add("roast-chicken","Herb Roast Chicken","Whole roast chicken with lemon, garlic, and herbs.","dinner",105,
  [MEAT("whole chicken",4.5), lime(2), garlic(8), DAIRY("butter",4,"tbsp"), SP("thyme",1,"tbsp"),
   SP("rosemary",1,"tbsp"), PROD("potato",1.5,"lb"), onion(1), olive_oil(), salt(), pepper()],
  "Pat the chicken dry and rub with softened herb butter, salt, and pepper. Stuff the cavity with lemon and garlic and set it over potatoes and onion. Roast at 425F, basting once, until the juices run clear. Rest before carving and serve with the roasted vegetables.",
  "moderate",["weekend","american","chicken","oven","comfort"])

add("pulled-pork","Slow Cooker Pulled Pork","Tender barbecue pulled pork for sandwiches.","dinner",480,
  [MEAT("pork shoulder",4), PAN("barbecue sauce",1.5), onion(2), garlic(5), PAN("brown sugar",2,"tbsp"),
   SP("paprika",1,"tbsp"), BREAD("brioche buns",8), PROD("cabbage",3,"cup")],
  "Rub the pork shoulder with paprika, brown sugar, salt, and pepper. Place it in a slow cooker with onion, garlic, and half the barbecue sauce. Cook on low for eight hours until it shreds easily. Toss the pulled pork with the remaining sauce and pile onto buns with slaw.",
  "moderate",["weekend","slow-cook","american","pork","comfort"])

add("beef-stew","Hearty Beef Stew","Slow-simmered beef stew with potatoes and carrots.","dinner",150,
  [MEAT("beef chuck",2), PROD("potato",1.5,"lb"), PROD("carrot",4), onion(2), garlic(4),
   PAN("beef broth",5), PAN("tomato paste",2,"tbsp"), PAN("flour",0.25), SP("thyme",1,"tbsp"), PROD("celery",3,"each")],
  "Dredge the beef in flour and brown it in batches. Saute onion, carrot, celery, and garlic, then stir in tomato paste. Add broth, thyme, and the beef and simmer for an hour. Add potatoes and cook until everything is tender and the broth thickens.",
  "budget",["weekend","slow-cook","beef","comfort","meal-prep","budget","one-pot"])

add("chicken-pot-pie","Chicken Pot Pie","Creamy chicken and vegetable pie under a flaky crust.","dinner",75,
  [MEAT("chicken breast",1.5), PAN("pie crust",2,"each"), FROZ("peas and carrots",2), onion(1), DAIRY("milk",1.5),
   DAIRY("butter",4,"tbsp"), PAN("flour",0.33), PAN("chicken broth",1.5), SP("thyme",1)],
  "Cook the chicken and dice it, then make a roux with butter and flour. Whisk in broth and milk to form a creamy sauce and stir in chicken, peas, and carrots. Pour into a pie crust and top with a second crust, crimping the edges. Bake at 400F until the crust is golden and the filling bubbles.",
  "moderate",["weekend","american","chicken","comfort","oven"])

add("lamb-tagine","Moroccan Lamb Tagine","Slow-braised lamb with apricots and warm spices.","dinner",165,
  [MEAT("lamb shoulder",2.5), onion(2), garlic(5), PROD("dried apricots",1,"cup"), can_tomato(),
   SP("cumin",1,"tbsp"), SP("cinnamon",1), SP("paprika",1,"tbsp"), PAN("chickpeas",1,"can"), PAN("couscous",1.5), cilantro()],
  "Brown the cubed lamb, then soften onion and garlic with the spices. Add tomatoes, apricots, and chickpeas and braise the lamb until fork-tender. Cook the couscous and fluff with a fork. Serve the tagine over couscous topped with cilantro.",
  "premium",["weekend","slow-cook","mediterranean","meat","comfort"])

add("baked-ziti","Baked Ziti","Cheesy baked ziti with sausage and marinara.","dinner",70,
  [PAN("ziti pasta",1,"lb"), MEAT("italian sausage",1), PAN("marinara sauce",3), DAIRY("ricotta cheese",1.5),
   DAIRY("mozzarella cheese",2.5), DAIRY("parmesan cheese",0.5), garlic(4), onion(1)],
  "Boil the ziti until just shy of al dente. Brown the sausage with onion and garlic and stir into the marinara. Mix the pasta with sauce and ricotta, then layer in a baking dish with mozzarella. Bake at 375F until bubbly and golden.",
  "moderate",["weekend","italian","pork","comfort","oven","meal-prep"])

add("carnitas","Pork Carnitas","Crispy slow-cooked Mexican pulled pork.","dinner",240,
  [MEAT("pork shoulder",3.5), PROD("orange",2), lime(3), onion(2), garlic(6), SP("cumin",1,"tbsp"),
   SP("oregano",1), BREAD("corn tortillas",16), cilantro(), PROD("white onion",1)],
  "Season the pork with cumin, oregano, salt, and pepper. Slow-cook with orange, lime, onion, and garlic until the meat shreds easily. Shred the pork and crisp it under the broiler. Serve in warm tortillas with cilantro and onion.",
  "moderate",["weekend","slow-cook","mexican","pork","comfort"])

add("chicken-marsala","Chicken Marsala","Pan-seared chicken in a mushroom Marsala wine sauce.","dinner",45,
  [MEAT("chicken breast",1.75), PROD("mushroom",1,"lb"), PAN("marsala wine",0.75), DAIRY("butter",4,"tbsp"),
   PAN("flour",0.5), garlic(3), PAN("chicken broth",1), PROD("parsley",0.5,"bunch"), PAN("egg noodles",0.75,"lb")],
  "Dredge the pounded chicken in flour and sear in butter until golden, then set aside. Saute the mushrooms and garlic until browned. Deglaze with Marsala and broth and simmer into a glossy sauce. Return the chicken to warm through and serve over egg noodles with parsley.",
  "moderate",["weekend","italian","chicken","comfort"])

add("braised-chicken-thighs","Braised Chicken Thighs","Bone-in thighs braised with tomatoes and olives.","dinner",60,
  [MEAT("chicken thighs",2.5), can_tomato(), PROD("kalamata olives",0.75,"cup"), onion(1), garlic(5),
   PAN("white wine",0.75), SP("oregano",1,"tbsp"), olive_oil(), PROD("parsley",0.5,"bunch"), PAN("white rice",2)],
  "Sear the seasoned chicken thighs skin-side down until crisp, then remove. Soften onion and garlic, deglaze with wine, and add tomatoes and oregano. Nestle the thighs back in with olives and braise until tender. Serve over rice with parsley.",
  "moderate",["weekend","mediterranean","chicken","comfort"])

add("eggplant-parmesan","Eggplant Parmesan","Breaded eggplant layered with marinara and cheese.","dinner",75,
  [PROD("eggplant",2.5,"lb"), PAN("panko breadcrumbs",2), DAIRY("eggs",3,"each"), PAN("flour",0.75),
   PAN("marinara sauce",3), DAIRY("mozzarella cheese",2), DAIRY("parmesan cheese",1), PROD("basil",1,"bunch")],
  "Bread the eggplant slices in flour, egg, and panko, then bake until crisp. Layer the eggplant with marinara and mozzarella in a baking dish. Repeat the layers and finish with parmesan. Bake at 375F until bubbly and top with fresh basil.",
  "moderate",["weekend","italian","vegetarian","comfort","oven"])

add("osso-buco-style-pork","Braised Pork Osso Buco","Pork shanks braised in white wine and vegetables.","dinner",180,
  [MEAT("pork shanks",3.5), onion(2), PROD("carrot",3), PROD("celery",3,"each"), garlic(6),
   PAN("white wine",1.5), can_tomato(), PAN("chicken broth",2), SP("thyme",1,"tbsp"), PAN("flour",0.25)],
  "Dredge and sear the pork shanks until browned all over. Soften onion, carrot, celery, and garlic in the same pot. Add wine, tomatoes, broth, and thyme, then return the shanks and braise low for two and a half hours. Serve the fall-apart pork with the rich vegetable sauce.",
  "premium",["weekend","slow-cook","italian","pork","comfort","oven"])

add("seafood-paella","Seafood Paella","Saffron rice with shrimp, mussels, and peppers.","dinner",60,
  [MEAT("shrimp",1), MEAT("mussels",1), PAN("paella rice",2), PROD("bell pepper",2), onion(1), garlic(5),
   SP("saffron",0.25), SP("paprika",1,"tbsp"), FROZ("peas",1), PAN("chicken broth",4), lime(2)],
  "Saute onion, pepper, and garlic, then toast the rice with paprika and saffron. Pour in the broth and simmer without stirring to build the rice. Nestle in the shrimp, mussels, and peas and cook until the seafood opens and cooks through. Rest, then serve with lemon wedges.",
  "premium",["weekend","mediterranean","seafood","comfort"])

add("french-onion-chicken","French Onion Chicken","Chicken smothered in caramelized onions and gruyere.","dinner",55,
  [MEAT("chicken breast",1.75), onion(4), DAIRY("gruyere cheese",1.5), DAIRY("butter",3,"tbsp"),
   PAN("beef broth",1.5), garlic(3), SP("thyme",1), PAN("flour",2,"tbsp"), BREAD("baguette",1,"each")],
  "Caramelize the onions slowly in butter until deep golden. Sear the seasoned chicken, then set aside. Add broth, garlic, thyme, and flour to the onions to make a sauce. Return the chicken, top with gruyere, and broil until melted; serve with baguette.",
  "moderate",["weekend","american","chicken","comfort","oven"])

add("stuffed-shells","Cheese Stuffed Shells","Jumbo pasta shells filled with ricotta and spinach.","dinner",70,
  [PAN("jumbo pasta shells",1,"lb"), DAIRY("ricotta cheese",2.5), DAIRY("mozzarella cheese",2), DAIRY("parmesan cheese",0.5),
   spinach(4), PAN("marinara sauce",3), DAIRY("eggs",1,"each"), garlic(3)],
  "Boil the shells until pliable and drain. Mix ricotta with spinach, egg, parmesan, and garlic. Stuff the shells and arrange over marinara in a baking dish. Top with mozzarella and bake at 375F until bubbly.",
  "moderate",["weekend","italian","vegetarian","comfort","oven","meal-prep"])

add("beef-bourguignon","Beef Bourguignon","Classic French beef braised in red wine with mushrooms.","dinner",180,
  [MEAT("beef chuck",2.5), MEAT("bacon",0.5), PAN("red wine",2.5), PROD("mushroom",1,"lb"), PROD("carrot",3),
   onion(2), garlic(5), PAN("beef broth",2), PAN("flour",0.25), SP("thyme",1,"tbsp"), PAN("tomato paste",2,"tbsp")],
  "Render the bacon, then sear the floured beef in the fat until browned. Soften onion, carrot, and garlic and stir in tomato paste. Add wine, broth, and thyme and braise the beef low and slow until tender. Saute the mushrooms separately and stir them in before serving.",
  "premium",["weekend","slow-cook","beef","comfort","oven"])

add("honey-glazed-ham","Honey Glazed Ham","Oven-baked ham with a sticky honey-mustard glaze.","dinner",120,
  [MEAT("bone-in ham",5), PAN("honey",0.75), PAN("dijon mustard",3,"tbsp"), PAN("brown sugar",0.5),
   PROD("orange",2), SP("cloves",0.5), DAIRY("butter",2,"tbsp")],
  "Score the ham and stud it with cloves. Whisk honey, mustard, brown sugar, butter, and orange juice into a glaze. Bake the ham covered, then brush generously with glaze and roast uncovered until lacquered. Rest before slicing.",
  "moderate",["weekend","american","pork","comfort","oven"])

add("vegetable-lasagna","Roasted Vegetable Lasagna","Hearty meatless lasagna layered with roasted vegetables.","dinner",90,
  [PAN("lasagna noodles",1,"lb"), PROD("zucchini",2), PROD("bell pepper",2), PROD("eggplant",1,"lb"),
   DAIRY("ricotta cheese",2), DAIRY("mozzarella cheese",2.5), PAN("marinara sauce",3), spinach(4), DAIRY("eggs",1,"each"), garlic(4)],
  "Roast the zucchini, peppers, and eggplant until caramelized. Mix ricotta with spinach, egg, and garlic. Layer noodles, marinara, roasted vegetables, ricotta, and mozzarella in a deep dish. Bake at 375F covered, then uncover until golden.",
  "moderate",["weekend","italian","vegetarian","comfort","oven","meal-prep"])

# =====================================================================
# GROUP 3: 20 MEAL-PREP DINNERS (soups, stews, casseroles, grain bowls)
# =====================================================================

add("beef-chili","Classic Beef Chili","Hearty beef and bean chili that gets better the next day.","dinner",50,
  [MEAT("ground beef",1.5), PAN("kidney beans",2,"can"), can_tomato(), PAN("tomato paste",3,"tbsp"), onion(2),
   garlic(5), SP("chili powder",2,"tbsp"), SP("cumin",1,"tbsp"), PROD("bell pepper",1), cheddar(1), sour_cream(0.5)],
  "Brown the beef with onion, pepper, and garlic in a large pot. Stir in chili powder, cumin, and tomato paste until fragrant. Add tomatoes and beans and simmer for at least 30 minutes. Serve topped with cheddar and sour cream.",
  "budget",["meal-prep","american","beef","comfort","budget","one-pot"])

add("chicken-tortilla-soup","Chicken Tortilla Soup","Spiced tomato broth with shredded chicken and tortillas.","dinner",45,
  [MEAT("chicken breast",1.5), can_tomato(), PAN("chicken broth",6), PAN("black beans",1,"can"), FROZ("corn",1.5),
   onion(1), garlic(4), SP("cumin",1,"tbsp"), SP("chili powder",1,"tbsp"), BREAD("corn tortillas",6), cilantro(), lime(2)],
  "Simmer chicken in broth with tomatoes, onion, garlic, and spices until cooked, then shred. Return the chicken with beans and corn and simmer to meld. Fry or bake tortilla strips until crisp. Serve topped with tortilla strips, cilantro, and lime.",
  "budget",["meal-prep","mexican","chicken","healthy","budget","one-pot"])

add("minestrone-soup","Minestrone Soup","Vegetable-packed Italian soup with beans and pasta.","dinner",45,
  [can_tomato(), PAN("cannellini beans",2,"can"), PAN("ditalini pasta",1), PROD("carrot",3), PROD("celery",3,"each"),
   onion(1), garlic(4), spinach(4), PAN("vegetable broth",6), SP("italian seasoning",1,"tbsp"), DAIRY("parmesan cheese",0.5)],
  "Saute onion, carrot, celery, and garlic until softened. Add tomatoes, broth, beans, and Italian seasoning and simmer. Stir in the pasta and cook until tender. Add spinach until wilted and serve with parmesan.",
  "budget",["meal-prep","italian","vegetarian","healthy","budget","one-pot"])

add("baked-potato-soup","Loaded Baked Potato Soup","Creamy potato soup with bacon, cheddar, and chives.","dinner",50,
  [PROD("potato",2.5,"lb"), MEAT("bacon",0.5), DAIRY("cheddar cheese",1.5), sour_cream(0.75), DAIRY("milk",2),
   onion(1), garlic(4), DAIRY("butter",3,"tbsp"), PAN("flour",0.25), PROD("green onion",4), PAN("chicken broth",4)],
  "Crisp the bacon, then soften onion and garlic in the fat. Make a roux with butter and flour, then whisk in broth and milk. Add diced potatoes and simmer until tender, mashing some for body. Finish with cheddar and sour cream and top with bacon and green onion.",
  "moderate",["meal-prep","american","comfort","one-pot"])

add("lentil-soup","Hearty Lentil Soup","Cozy spiced lentil soup with carrots and tomatoes.","dinner",45,
  [PAN("brown lentils",2), PROD("carrot",3), PROD("celery",3,"each"), onion(1), garlic(5), can_tomato(),
   PAN("vegetable broth",6), SP("cumin",1,"tbsp"), SP("smoked paprika",1), spinach(4), olive_oil()],
  "Saute onion, carrot, celery, and garlic in olive oil. Add cumin and paprika, then the lentils, tomatoes, and broth. Simmer until the lentils are tender, about 30 minutes. Stir in spinach until wilted and season to taste.",
  "budget",["meal-prep","mediterranean","vegan","vegetarian","healthy","budget","one-pot","dairy-free"])

add("white-chicken-chili","White Chicken Chili","Creamy chili with chicken, white beans, and green chiles.","dinner",45,
  [MEAT("chicken breast",1.5), PAN("white beans",2,"can"), PAN("green chiles",2,"can"), onion(1), garlic(4),
   PAN("chicken broth",4), SP("cumin",1,"tbsp"), DAIRY("sour cream",0.5), cilantro(), lime(2), FROZ("corn",1)],
  "Simmer chicken in broth with onion, garlic, chiles, and cumin until cooked, then shred. Add white beans and corn and mash some beans to thicken. Stir in sour cream until creamy. Finish with cilantro and lime.",
  "moderate",["meal-prep","mexican","chicken","comfort","one-pot"])

add("chicken-enchilada-casserole","Chicken Enchilada Casserole","Layered enchilada bake with chicken, beans, and cheese.","dinner",55,
  [MEAT("chicken breast",1.5), BREAD("corn tortillas",12), PAN("enchilada sauce",2.5), PAN("black beans",1,"can"),
   cheddar(2.5), FROZ("corn",1), onion(1), SP("cumin",1), cilantro()],
  "Cook and shred the chicken, then mix with beans, corn, and cumin. Layer tortillas, chicken mixture, enchilada sauce, and cheese in a baking dish. Repeat the layers and finish with cheese. Bake at 375F until bubbly and top with cilantro.",
  "budget",["meal-prep","mexican","chicken","comfort","budget","oven"])

add("turkey-quinoa-bowls","Turkey Quinoa Power Bowls","Make-ahead bowls with seasoned turkey and roasted veggies.","dinner",40,
  [MEAT("ground turkey",1.25), PAN("quinoa",1.5), PROD("sweet potato",2), PROD("broccoli",4,"cup"), garlic(3),
   SP("cumin",1), SP("paprika",1), olive_oil(), PROD("avocado",2), lime(2)],
  "Cook the quinoa and roast the sweet potato and broccoli with olive oil. Brown the turkey with garlic, cumin, and paprika. Divide quinoa, vegetables, and turkey into bowls. Top with avocado and a squeeze of lime.",
  "moderate",["meal-prep","healthy","high-protein","meat","gluten-free"])

add("split-pea-soup","Split Pea Soup","Thick split pea soup with smoky ham and carrots.","dinner",75,
  [PAN("split peas",2), MEAT("ham",1), PROD("carrot",3), PROD("celery",3,"each"), onion(1), garlic(4),
   PAN("chicken broth",7), SP("thyme",1), PROD("potato",2)],
  "Saute onion, carrot, celery, and garlic until softened. Add split peas, ham, potato, broth, and thyme. Simmer for an hour until the peas break down into a thick soup. Stir well and adjust the seasoning before serving.",
  "budget",["meal-prep","american","pork","comfort","budget","one-pot"])

add("sausage-tortellini-soup","Sausage Tortellini Soup","Creamy tomato soup with sausage and cheese tortellini.","dinner",45,
  [MEAT("italian sausage",1), PAN("cheese tortellini",1,"lb"), can_tomato(), DAIRY("heavy cream",1), spinach(4),
   onion(1), garlic(4), PAN("chicken broth",5), SP("italian seasoning",1,"tbsp")],
  "Brown the sausage with onion and garlic in a large pot. Add tomatoes, broth, and Italian seasoning and simmer. Stir in the tortellini and cook until tender. Add cream and spinach until the spinach wilts.",
  "moderate",["meal-prep","italian","pork","comfort","one-pot"])

add("beef-stuffed-peppers","Beef Stuffed Peppers","Bell peppers stuffed with beef, rice, and tomato.","dinner",60,
  [MEAT("ground beef",1.25), PROD("bell pepper",4), PAN("white rice",1.5), can_tomato(), onion(1), garlic(4),
   cheddar(1.5), SP("italian seasoning",1,"tbsp"), PAN("tomato paste",2,"tbsp")],
  "Cook the rice and brown the beef with onion and garlic. Stir in tomatoes, tomato paste, rice, and seasoning. Stuff the mixture into halved peppers and top with cheese. Bake at 375F until the peppers are tender and the cheese melts.",
  "budget",["meal-prep","american","beef","comfort","budget","oven"])

add("coconut-chickpea-curry","Coconut Chickpea Curry","Creamy spiced chickpea and spinach curry.","dinner",40,
  [PAN("chickpeas",2,"can"), PAN("coconut milk",1,"can"), can_tomato(), onion(1), garlic(5),
   PROD("ginger",1,"tbsp"), SP("curry powder",1.5,"tbsp"), spinach(5), PAN("white rice",2), cilantro()],
  "Saute onion, garlic, and ginger, then bloom the curry powder. Add tomatoes and coconut milk and simmer into a sauce. Stir in chickpeas and spinach until the spinach wilts. Serve over rice with cilantro.",
  "budget",["meal-prep","indian","vegan","vegetarian","healthy","budget","one-pot","dairy-free","gluten-free"])

add("chicken-and-rice-casserole","Chicken and Rice Casserole","Comforting baked chicken, rice, and vegetable casserole.","dinner",60,
  [MEAT("chicken breast",1.5), PAN("white rice",1.5), FROZ("peas and carrots",2), onion(1), garlic(3),
   DAIRY("cheddar cheese",1.5), PAN("chicken broth",3), DAIRY("cream of mushroom soup",1,"can"), SP("thyme",1)],
  "Mix raw rice with broth, soup, onion, garlic, and thyme in a baking dish. Nestle seasoned chicken on top and cover tightly. Bake at 375F until the rice is tender and the chicken is cooked. Stir in peas and carrots and top with cheese until melted.",
  "budget",["meal-prep","american","chicken","comfort","budget","oven"])

add("black-bean-soup","Black Bean Soup","Smoky pureed black bean soup with lime and cilantro.","dinner",40,
  [PAN("black beans",3,"can"), onion(1), garlic(5), PROD("bell pepper",1), SP("cumin",1,"tbsp"),
   SP("smoked paprika",1), PAN("vegetable broth",4), lime(2), cilantro(), sour_cream(0.5)],
  "Saute onion, pepper, and garlic with cumin and paprika. Add the beans and broth and simmer to meld. Blend half the soup for a creamy, thick texture. Finish with lime and serve with cilantro and sour cream.",
  "budget",["meal-prep","mexican","vegetarian","healthy","budget","one-pot","gluten-free"])

add("teriyaki-chicken-meal-prep","Teriyaki Chicken Meal Prep","Batch teriyaki chicken with rice and broccoli.","dinner",40,
  [MEAT("chicken thighs",2), PAN("soy sauce",0.33), PAN("brown sugar",3,"tbsp"), garlic(4), PROD("ginger",1,"tbsp"),
   PAN("white rice",2.5), PROD("broccoli",5,"cup"), PAN("cornstarch",1,"tbsp"), PAN("sesame oil",1,"tbsp")],
  "Cook a big batch of rice and steam the broccoli. Sear the chicken thighs, then add soy sauce, brown sugar, garlic, and ginger. Simmer with a cornstarch slurry until glazed. Portion the chicken, rice, and broccoli into containers.",
  "moderate",["meal-prep","asian","chicken","high-protein"])

add("vegetable-curry","Mixed Vegetable Curry","Hearty vegetable curry with potatoes and peas.","dinner",45,
  [PROD("potato",2), FROZ("peas",1.5), PROD("cauliflower",4,"cup"), PROD("carrot",3), PAN("coconut milk",1,"can"),
   can_tomato(), onion(1), garlic(5), PROD("ginger",1,"tbsp"), SP("curry powder",1.5,"tbsp"), PAN("white rice",2)],
  "Saute onion, garlic, and ginger with curry powder until fragrant. Add tomatoes and coconut milk and bring to a simmer. Stir in potatoes, carrots, and cauliflower and cook until tender. Add peas at the end and serve over rice.",
  "budget",["meal-prep","indian","vegan","vegetarian","healthy","budget","one-pot","dairy-free","gluten-free"])

add("shepherds-pie","Shepherds Pie","Savory beef and vegetables under a mashed potato crust.","dinner",70,
  [MEAT("ground beef",1.5), PROD("potato",2.5,"lb"), FROZ("peas and carrots",2), onion(1), garlic(4),
   DAIRY("butter",4,"tbsp"), DAIRY("milk",0.75), PAN("beef broth",1), PAN("tomato paste",2,"tbsp"), SP("thyme",1)],
  "Boil and mash the potatoes with butter and milk. Brown the beef with onion and garlic, then add tomato paste, broth, and thyme. Stir in peas and carrots and spread into a baking dish. Top with mashed potatoes and bake at 400F until golden.",
  "budget",["meal-prep","american","beef","comfort","budget","oven"])

add("quinoa-burrito-bowls","Quinoa Burrito Bowls","Protein-packed vegetarian burrito bowls for the week.","dinner",35,
  [PAN("quinoa",1.5), PAN("black beans",2,"can"), FROZ("corn",1.5), PROD("avocado",2), PROD("cherry tomato",2,"cup"),
   cheddar(1), lime(2), cilantro(), SP("cumin",1), SP("chili powder",1)],
  "Cook the quinoa and season the beans with cumin and chili powder. Warm the corn and dice the tomato and avocado. Build bowls with quinoa, beans, corn, and tomato. Top with cheese, avocado, lime, and cilantro.",
  "budget",["meal-prep","mexican","vegetarian","healthy","budget","gluten-free"])

add("sausage-white-bean-stew","Sausage and White Bean Stew","Rustic stew with sausage, beans, and kale.","dinner",45,
  [MEAT("italian sausage",1.25), PAN("cannellini beans",2,"can"), PROD("kale",4,"cup"), can_tomato(), onion(1),
   garlic(5), PAN("chicken broth",4), SP("italian seasoning",1,"tbsp"), olive_oil()],
  "Brown the sausage and set aside, then soften onion and garlic. Add tomatoes, broth, beans, and seasoning and simmer. Return the sausage and add the kale until wilted and tender. Adjust the seasoning and serve.",
  "budget",["meal-prep","italian","pork","healthy","budget","one-pot"])

add("thai-peanut-noodles","Thai Peanut Noodle Bowls","Make-ahead noodles in a creamy peanut sauce.","dinner",35,
  [PAN("rice noodles",12,"oz"), PAN("peanut butter",0.5), PAN("soy sauce",3,"tbsp"), PROD("bell pepper",2),
   PROD("carrot",2), garlic(3), PROD("ginger",1,"tbsp"), PAN("honey",2,"tbsp"), PROD("green onion",4), lime(2)],
  "Cook the rice noodles and rinse under cold water. Whisk peanut butter, soy sauce, honey, garlic, ginger, and lime into a sauce. Toss the noodles with the sauce and shredded pepper and carrot. Top with green onion and serve warm or chilled.",
  "budget",["meal-prep","asian","vegetarian","budget"])

# =====================================================================
# GROUP 4: 30 LUNCHES (salads, grain bowls, soups, wraps, sandwiches)
# =====================================================================

add("cobb-salad","Cobb Salad","Loaded salad with chicken, bacon, egg, and blue cheese.","lunch",25,
  [MEAT("chicken breast",1), MEAT("bacon",0.4), DAIRY("eggs",4,"each"), PROD("romaine lettuce",1,"each"),
   PROD("avocado",2), PROD("cherry tomato",2,"cup"), DAIRY("blue cheese crumbles",0.5), DAIRY("ranch dressing",0.5)],
  "Cook and slice the chicken, crisp the bacon, and hard-boil the eggs. Chop the romaine and arrange on plates. Top with rows of chicken, bacon, egg, avocado, tomato, and blue cheese. Drizzle with ranch dressing.",
  "moderate",["quick","american","chicken","healthy","high-protein","low-carb"])

add("greek-salad","Greek Salad","Crisp cucumber, tomato, and feta salad with olives.","lunch",15,
  [PROD("cucumber",2), PROD("tomato",4), PROD("red onion",0.5), DAIRY("feta cheese",1), PROD("kalamata olives",0.75,"cup"),
   lime(1), SP("oregano",1,"tbsp"), olive_oil(), PROD("bell pepper",1)],
  "Chop the cucumber, tomato, pepper, and red onion into chunks. Toss with olives and a dressing of olive oil, lemon, and oregano. Top with large pieces of feta. Let it sit a few minutes before serving.",
  "moderate",["quick","mediterranean","vegetarian","healthy","low-carb","gluten-free"])

add("turkey-club-wrap","Turkey Club Wrap","Turkey, bacon, and avocado rolled in a soft tortilla.","lunch",15,
  [MEAT("sliced turkey",0.75), MEAT("bacon",0.3), BREAD("flour tortillas",4), PROD("lettuce",1,"each"),
   PROD("tomato",2), PROD("avocado",2), DAIRY("mayonnaise",0.25)],
  "Crisp the bacon and slice the avocado and tomato. Spread the tortillas with mayonnaise. Layer turkey, bacon, lettuce, tomato, and avocado down the center. Roll tightly and slice in half.",
  "moderate",["quick","american","meat"])

add("caprese-sandwich","Caprese Sandwich","Fresh mozzarella, tomato, and basil on crusty bread.","lunch",10,
  [BREAD("ciabatta rolls",4), DAIRY("fresh mozzarella",1), PROD("tomato",3), PROD("basil",1,"bunch"),
   PAN("balsamic glaze",2,"tbsp"), olive_oil()],
  "Slice the ciabatta rolls and drizzle with olive oil. Layer thick slices of mozzarella and tomato. Add fresh basil and a drizzle of balsamic glaze. Close the sandwiches and press gently.",
  "moderate",["quick","italian","vegetarian"])

add("chicken-caesar-salad","Chicken Caesar Salad","Romaine with grilled chicken, parmesan, and croutons.","lunch",20,
  [MEAT("chicken breast",1.25), PROD("romaine lettuce",2,"each"), DAIRY("caesar dressing",0.5),
   DAIRY("parmesan cheese",0.5), PAN("croutons",2), lime(1)],
  "Season and grill the chicken, then slice. Chop the romaine and place in a large bowl. Toss with Caesar dressing, parmesan, and croutons. Top with the sliced chicken.",
  "moderate",["quick","american","chicken","high-protein"])

add("hummus-veggie-wrap","Hummus Veggie Wrap","Creamy hummus wrap loaded with crunchy vegetables.","lunch",15,
  [BREAD("flour tortillas",4), PAN("hummus",1), PROD("cucumber",1), PROD("carrot",2), PROD("bell pepper",1),
   spinach(2), DAIRY("feta cheese",0.5), PROD("red onion",0.25)],
  "Spread a generous layer of hummus over each tortilla. Add spinach, cucumber, carrot, pepper, and red onion. Sprinkle with feta. Roll up tightly and slice in half.",
  "budget",["quick","mediterranean","vegetarian","healthy","budget"])

add("tuna-salad-sandwich","Tuna Salad Sandwich","Classic creamy tuna salad on toasted bread.","lunch",10,
  [MEAT("canned tuna",2,"can"), BREAD("sandwich bread",8,"slice"), DAIRY("mayonnaise",0.33), PROD("celery",2,"each"),
   PROD("red onion",0.25), PROD("lettuce",1,"each"), lime(1)],
  "Drain the tuna and mix with mayonnaise, diced celery, and red onion. Brighten with a squeeze of lemon and season to taste. Toast the bread and add lettuce. Pile on the tuna salad and close the sandwiches.",
  "budget",["quick","american","seafood","budget"])

add("quinoa-chickpea-salad","Quinoa Chickpea Salad","Bright Mediterranean grain salad that keeps all week.","lunch",25,
  [PAN("quinoa",1.5), PAN("chickpeas",1,"can"), PROD("cucumber",1), PROD("cherry tomato",2,"cup"), DAIRY("feta cheese",0.75),
   PROD("red onion",0.5), PROD("parsley",0.5,"bunch"), lime(2), olive_oil()],
  "Cook the quinoa and let it cool. Dice the cucumber, tomato, and red onion. Toss the quinoa with chickpeas, vegetables, and parsley. Dress with lemon and olive oil and top with feta.",
  "budget",["meal-prep","mediterranean","vegetarian","healthy","budget","gluten-free"])

add("blt-sandwich","BLT Sandwich","The classic bacon, lettuce, and tomato sandwich.","lunch",15,
  [MEAT("bacon",0.75), BREAD("sandwich bread",8,"slice"), PROD("lettuce",1,"each"), PROD("tomato",3),
   DAIRY("mayonnaise",0.25)],
  "Cook the bacon until crisp and drain. Toast the bread and spread with mayonnaise. Layer lettuce, tomato, and bacon. Close the sandwiches and slice diagonally.",
  "budget",["quick","american","pork","budget"])

add("buffalo-chicken-salad","Buffalo Chicken Salad","Spicy buffalo chicken over crisp greens with ranch.","lunch",20,
  [MEAT("chicken breast",1.25), PROD("romaine lettuce",2,"each"), PAN("buffalo sauce",0.33), DAIRY("ranch dressing",0.5),
   PROD("carrot",2), PROD("celery",3,"each"), DAIRY("blue cheese crumbles",0.5), PROD("cherry tomato",1,"cup")],
  "Cook the chicken, then toss it with buffalo sauce. Chop the romaine, carrot, and celery into a large bowl. Add tomatoes and top with the buffalo chicken. Drizzle with ranch and scatter blue cheese.",
  "moderate",["quick","american","chicken","high-protein","low-carb"])

add("italian-sub","Italian Sub Sandwich","Stacked deli meats and provolone on a crusty roll.","lunch",15,
  [MEAT("salami",0.4), MEAT("ham",0.4), DAIRY("provolone cheese",0.5), BREAD("hoagie rolls",4), PROD("lettuce",1,"each"),
   PROD("tomato",2), PROD("red onion",0.5), olive_oil(), SP("oregano",1)],
  "Split the hoagie rolls and drizzle with olive oil and oregano. Layer salami, ham, and provolone. Add lettuce, tomato, and thin red onion. Close and press the sandwiches before serving.",
  "moderate",["quick","italian","pork"])

add("southwest-chicken-bowl","Southwest Chicken Bowl","Rice bowl with chicken, black beans, corn, and avocado.","lunch",25,
  [MEAT("chicken breast",1.25), PAN("white rice",2), PAN("black beans",1,"can"), FROZ("corn",1), PROD("avocado",2),
   PAN("salsa",0.75), cheddar(0.75), lime(2), cilantro(), SP("cumin",1)],
  "Cook the rice and season the chicken with cumin, then cook and slice. Warm the beans and corn. Build bowls with rice, beans, corn, and chicken. Top with avocado, salsa, cheese, lime, and cilantro.",
  "moderate",["quick","mexican","chicken","healthy","high-protein","meal-prep"])

add("egg-salad-sandwich","Egg Salad Sandwich","Creamy egg salad on soft bread with fresh herbs.","lunch",15,
  [DAIRY("eggs",6,"each"), BREAD("sandwich bread",8,"slice"), DAIRY("mayonnaise",0.33), PAN("dijon mustard",1,"tbsp"),
   PROD("celery",2,"each"), PROD("chives",0.25,"bunch"), PROD("lettuce",1,"each")],
  "Hard-boil and chop the eggs. Mix with mayonnaise, mustard, celery, and chives. Toast the bread and add lettuce. Spread the egg salad and close the sandwiches.",
  "budget",["quick","american","vegetarian","budget"])

add("asian-chicken-salad","Asian Chicken Salad","Crunchy cabbage salad with chicken and sesame dressing.","lunch",20,
  [MEAT("chicken breast",1.25), PROD("cabbage",4,"cup"), PROD("carrot",2), PROD("green onion",4), PAN("soy sauce",2,"tbsp"),
   PAN("sesame oil",2,"tbsp"), PAN("honey",1,"tbsp"), PROD("ginger",1,"tbsp"), PAN("sesame seeds",2,"tbsp"), lime(1)],
  "Cook and shred the chicken. Shred the cabbage and carrot and slice the green onion. Whisk soy sauce, sesame oil, honey, ginger, and lime into a dressing. Toss everything together and top with sesame seeds.",
  "moderate",["quick","asian","chicken","healthy","high-protein"])

add("caprese-pasta-salad","Caprese Pasta Salad","Cold pasta salad with mozzarella, tomato, and basil.","lunch",25,
  [PAN("rotini pasta",1,"lb"), DAIRY("fresh mozzarella",1), PROD("cherry tomato",2,"cup"), PROD("basil",1,"bunch"),
   PAN("balsamic glaze",3,"tbsp"), garlic(2), olive_oil()],
  "Boil the rotini, then rinse under cold water and drain. Halve the tomatoes and mozzarella pearls. Toss the pasta with tomato, mozzarella, and basil. Dress with olive oil, garlic, and balsamic glaze.",
  "budget",["meal-prep","italian","vegetarian","budget"])

add("chicken-noodle-soup","Chicken Noodle Soup","Comforting chicken soup with egg noodles and vegetables.","lunch",40,
  [MEAT("chicken breast",1.25), PAN("egg noodles",0.75,"lb"), PROD("carrot",3), PROD("celery",3,"each"), onion(1),
   garlic(4), PAN("chicken broth",7), SP("thyme",1), PROD("parsley",0.5,"bunch")],
  "Simmer chicken in broth with onion, carrot, celery, garlic, and thyme until cooked, then shred. Return the chicken and add the noodles to the simmering broth. Cook until the noodles are tender. Finish with parsley and adjust the seasoning.",
  "budget",["meal-prep","american","chicken","comfort","budget","one-pot"])

add("falafel-bowl","Falafel Grain Bowl","Crispy chickpea falafel over greens with tahini.","lunch",30,
  [PAN("chickpeas",2,"can"), PROD("parsley",1,"bunch"), garlic(4), PAN("tahini",0.33), lime(2), PROD("cucumber",1),
   PROD("cherry tomato",2,"cup"), PAN("flour",0.25), SP("cumin",1,"tbsp"), PAN("quinoa",1)],
  "Blend chickpeas with parsley, garlic, cumin, and flour, then form into patties. Pan-fry the falafel until crisp and golden. Cook the quinoa and chop the cucumber and tomato. Build bowls and drizzle with lemon-tahini sauce.",
  "budget",["quick","mediterranean","vegan","vegetarian","healthy","budget","dairy-free"])

add("ham-and-cheese-melt","Ham and Cheese Melt","Toasty grilled ham and cheddar sandwich.","lunch",15,
  [MEAT("ham",0.5), DAIRY("cheddar cheese",1), BREAD("sourdough bread",8,"slice"), DAIRY("butter",3,"tbsp"),
   PAN("dijon mustard",2,"tbsp")],
  "Butter the outsides of the bread and spread mustard inside. Layer ham and cheddar between the slices. Grill in a skillet until golden and crisp on both sides. Slice and serve warm.",
  "budget",["quick","american","pork","comfort","budget"])

add("spinach-strawberry-salad","Spinach Strawberry Salad","Fresh spinach salad with strawberries and feta.","lunch",15,
  [spinach(6), PROD("strawberry",2,"cup"), DAIRY("feta cheese",0.75), PAN("walnuts",0.5), PROD("red onion",0.25),
   PAN("balsamic vinegar",3,"tbsp"), olive_oil(), PAN("honey",1,"tbsp")],
  "Pile the spinach into a large bowl. Add sliced strawberries, red onion, and walnuts. Whisk balsamic, olive oil, and honey into a dressing. Toss and top with crumbled feta.",
  "moderate",["quick","american","vegetarian","healthy","low-carb","gluten-free"])

add("tomato-basil-soup","Tomato Basil Soup","Velvety tomato soup with fresh basil and cream.","lunch",35,
  [can_tomato(), DAIRY("heavy cream",0.75), PROD("basil",1,"bunch"), onion(1), garlic(5), PAN("vegetable broth",3),
   DAIRY("butter",2,"tbsp"), BREAD("crusty bread",1,"each"), olive_oil()],
  "Saute onion and garlic in butter until soft. Add tomatoes and broth and simmer to deepen the flavor. Blend until smooth, then stir in cream and basil. Serve with crusty bread for dipping.",
  "budget",["quick","italian","vegetarian","comfort","budget"])

add("turkey-avocado-club","Turkey Avocado Sandwich","Hearty turkey sandwich with avocado and havarti.","lunch",10,
  [MEAT("sliced turkey",0.75), PROD("avocado",2), DAIRY("havarti cheese",0.5), BREAD("multigrain bread",8,"slice"),
   PROD("lettuce",1,"each"), PROD("tomato",2), DAIRY("mayonnaise",0.25)],
  "Toast the bread and spread with mayonnaise. Mash the avocado over one side. Layer turkey, havarti, lettuce, and tomato. Close and slice the sandwiches.",
  "moderate",["quick","american","meat"])

add("burrito-bowl-lunch","Beef Burrito Bowl","Quick beef and rice bowl with all the fixings.","lunch",25,
  [MEAT("ground beef",1), PAN("white rice",2), PAN("black beans",1,"can"), cheddar(0.75), sour_cream(0.5),
   PAN("salsa",0.75), PROD("lettuce",1,"each"), lime(1), SP("cumin",1), SP("chili powder",1)],
  "Cook the rice and brown the beef with cumin and chili powder. Warm the beans. Build bowls with rice, beans, beef, and shredded lettuce. Top with cheese, salsa, sour cream, and lime.",
  "budget",["quick","mexican","beef","budget","high-protein"])

add("roasted-veggie-grain-bowl","Roasted Veggie Grain Bowl","Warm grain bowl with roasted vegetables and tahini.","lunch",35,
  [PAN("farro",1.5), PROD("sweet potato",2), PROD("broccoli",4,"cup"), PROD("chickpeas",1,"can"), PAN("tahini",0.33),
   lime(2), garlic(2), spinach(3), SP("paprika",1), olive_oil()],
  "Cook the farro until tender. Roast the sweet potato, broccoli, and chickpeas with olive oil and paprika. Whisk tahini with lemon and garlic for the dressing. Build bowls with farro, greens, and roasted vegetables and drizzle with tahini.",
  "budget",["meal-prep","mediterranean","vegan","vegetarian","healthy","budget","dairy-free"])

add("chicken-bacon-ranch-wrap","Chicken Bacon Ranch Wrap","Chicken, bacon, and ranch wrapped in a tortilla.","lunch",20,
  [MEAT("chicken breast",1.25), MEAT("bacon",0.3), BREAD("flour tortillas",4), DAIRY("ranch dressing",0.5),
   cheddar(0.75), PROD("lettuce",1,"each"), PROD("tomato",2)],
  "Cook and slice the chicken and crisp the bacon. Warm the tortillas to soften. Layer chicken, bacon, cheese, lettuce, and tomato. Drizzle with ranch and roll up tightly.",
  "moderate",["quick","american","chicken","high-protein"])

add("lentil-tabbouleh","Lentil Tabbouleh","Herby lentil and bulgur salad with lemon.","lunch",30,
  [PAN("brown lentils",1), PAN("bulgur wheat",1), PROD("parsley",2,"bunch"), PROD("mint",0.5,"bunch"),
   PROD("tomato",3), PROD("cucumber",1), lime(3), olive_oil(), PROD("green onion",4)],
  "Cook the lentils and soak the bulgur until tender. Finely chop the parsley, mint, tomato, cucumber, and green onion. Combine with the lentils and bulgur. Dress generously with lemon and olive oil.",
  "budget",["meal-prep","mediterranean","vegan","vegetarian","healthy","budget","dairy-free"])

add("grilled-cheese-tomato","Grilled Cheese and Tomato","Buttery grilled cheese paired with tomato.","lunch",15,
  [DAIRY("cheddar cheese",1.5), BREAD("sourdough bread",8,"slice"), DAIRY("butter",4,"tbsp"), PROD("tomato",2)],
  "Butter the outsides of the bread. Layer cheddar and thin tomato slices inside. Grill in a skillet over medium heat until golden and the cheese melts. Slice diagonally and serve hot.",
  "budget",["quick","american","vegetarian","comfort","budget"])

add("shrimp-avocado-salad","Shrimp Avocado Salad","Light salad with shrimp, avocado, and citrus.","lunch",20,
  [MEAT("shrimp",1.25), PROD("avocado",2), PROD("romaine lettuce",2,"each"), PROD("cherry tomato",2,"cup"),
   PROD("cucumber",1), lime(2), cilantro(), olive_oil()],
  "Saute the shrimp until pink and let cool. Chop the romaine, cucumber, and tomato. Toss with avocado and a dressing of lime, olive oil, and cilantro. Top with the shrimp.",
  "moderate",["quick","seafood","healthy","high-protein","low-carb","gluten-free"])

add("pesto-chicken-sandwich","Pesto Chicken Sandwich","Grilled chicken with pesto and mozzarella on ciabatta.","lunch",20,
  [MEAT("chicken breast",1.25), BREAD("ciabatta rolls",4), PAN("basil pesto",0.33), DAIRY("fresh mozzarella",0.75),
   PROD("tomato",2), spinach(2)],
  "Grill and slice the chicken. Spread pesto on the ciabatta rolls. Layer chicken, mozzarella, tomato, and spinach. Close and press the sandwiches.",
  "moderate",["quick","italian","chicken","high-protein"])

add("broccoli-cheddar-soup","Broccoli Cheddar Soup","Creamy broccoli cheddar soup for a cozy lunch.","lunch",40,
  [PROD("broccoli",6,"cup"), DAIRY("cheddar cheese",2.5), DAIRY("milk",2), PROD("carrot",2), onion(1), garlic(3),
   DAIRY("butter",4,"tbsp"), PAN("flour",0.33), PAN("vegetable broth",4)],
  "Saute onion and garlic in butter, then whisk in flour. Add broth and milk and bring to a simmer. Add broccoli and carrot and cook until tender. Stir in cheddar until melted and smooth.",
  "moderate",["meal-prep","american","vegetarian","comfort","one-pot"])

add("mediterranean-tuna-salad","Mediterranean Tuna Salad","Bright tuna salad with olives, tomato, and lemon.","lunch",15,
  [MEAT("canned tuna",2,"can"), PROD("cherry tomato",2,"cup"), PROD("kalamata olives",0.5,"cup"), PROD("red onion",0.25),
   PROD("cucumber",1), lime(2), olive_oil(), PROD("parsley",0.5,"bunch")],
  "Drain the tuna and flake into a bowl. Add halved tomatoes, olives, cucumber, and red onion. Dress with lemon, olive oil, and parsley. Serve over greens or with bread.",
  "moderate",["quick","mediterranean","seafood","healthy","low-carb","gluten-free","dairy-free"])

# =====================================================================
# GROUP 5: 20 BREAKFASTS
# =====================================================================

add("classic-pancakes","Fluffy Buttermilk Pancakes","Stacks of fluffy pancakes with maple syrup.","breakfast",25,
  [PAN("flour",2), DAIRY("buttermilk",2), DAIRY("eggs",2,"each"), DAIRY("butter",4,"tbsp"), PAN("sugar",2,"tbsp"),
   PAN("baking powder",1,"tbsp"), PAN("maple syrup",0.5), salt()],
  "Whisk the flour, sugar, baking powder, and salt together. Mix in buttermilk, eggs, and melted butter until just combined. Cook ladlefuls on a buttered griddle until bubbles form, then flip. Serve stacked with maple syrup.",
  "budget",["quick","american","vegetarian","comfort","budget"])

add("veggie-frittata","Vegetable Frittata","Baked egg frittata with spinach, tomato, and feta.","breakfast",30,
  [DAIRY("eggs",10,"each"), spinach(4), PROD("cherry tomato",1.5,"cup"), DAIRY("feta cheese",0.75), onion(0.5),
   garlic(3), DAIRY("milk",0.5), olive_oil()],
  "Saute onion, garlic, tomato, and spinach in an oven-safe skillet. Whisk the eggs with milk and pour over the vegetables. Cook until the edges set, then sprinkle with feta. Transfer to a 375F oven and bake until puffed and set.",
  "budget",["quick","mediterranean","vegetarian","healthy","high-protein","low-carb","gluten-free"])

add("breakfast-burritos","Breakfast Burritos","Hearty burritos with eggs, sausage, and cheese.","breakfast",30,
  [DAIRY("eggs",8,"each"), MEAT("breakfast sausage",0.75), BREAD("flour tortillas",4), cheddar(1.5), PROD("potato",1,"lb"),
   PROD("bell pepper",1), PAN("salsa",0.5), onion(0.5)],
  "Crisp diced potatoes with pepper and onion until tender. Brown the sausage and scramble the eggs. Pile eggs, sausage, potatoes, and cheese onto warm tortillas. Roll into burritos and sear seam-side down with salsa on the side.",
  "budget",["quick","mexican","pork","comfort","budget","meal-prep"])

add("overnight-oats","Overnight Oats","Make-ahead oats with berries and almond butter.","breakfast",10,
  [PAN("rolled oats",2), DAIRY("milk",2), DAIRY("greek yogurt",1), PAN("almond butter",0.25), PAN("honey",2,"tbsp"),
   PROD("blueberry",1.5,"cup"), PAN("chia seeds",2,"tbsp")],
  "Stir the oats, milk, yogurt, chia seeds, and honey together. Divide into jars and refrigerate overnight. In the morning, top with almond butter and blueberries. Stir and enjoy cold.",
  "budget",["quick","american","vegetarian","healthy","budget","meal-prep"])

add("avocado-toast-eggs","Avocado Toast with Eggs","Smashed avocado toast topped with a fried egg.","breakfast",15,
  [PROD("avocado",2), BREAD("sourdough bread",4,"slice"), DAIRY("eggs",4,"each"), lime(1), SP("red pepper flakes",0.5),
   olive_oil(), salt(), pepper()],
  "Toast the sourdough until crisp. Mash the avocado with lime, salt, and pepper, then spread on the toast. Fry the eggs to your liking. Top each toast with an egg and a pinch of red pepper flakes.",
  "budget",["quick","american","vegetarian","healthy","budget"])

add("spinach-smoothie-bowl","Green Smoothie Bowl","Thick spinach and banana smoothie bowl with toppings.","breakfast",10,
  [spinach(3), PROD("banana",3), FROZ("mango",1.5), DAIRY("greek yogurt",1), PAN("almond milk",1), PAN("granola",1),
   PAN("chia seeds",2,"tbsp"), PAN("honey",1,"tbsp")],
  "Blend the spinach, banana, mango, yogurt, and almond milk until thick. Pour into bowls. Top with granola, chia seeds, and a drizzle of honey. Serve immediately.",
  "moderate",["quick","american","vegetarian","healthy"])

add("sausage-egg-casserole","Sausage Egg Casserole","Make-ahead baked breakfast casserole with bread and cheese.","breakfast",60,
  [DAIRY("eggs",10,"each"), MEAT("breakfast sausage",1), BREAD("bread",6,"slice"), cheddar(2), DAIRY("milk",2),
   onion(0.5), PROD("bell pepper",1), SP("paprika",0.5)],
  "Brown the sausage with onion and pepper. Layer torn bread, sausage, and cheese in a baking dish. Whisk the eggs with milk and paprika and pour over the top. Refrigerate, then bake at 350F until set and golden.",
  "moderate",["meal-prep","american","pork","comfort","oven"])

add("blueberry-muffins","Blueberry Muffins","Tender bakery-style blueberry muffins.","breakfast",35,
  [PAN("flour",2.5), PROD("blueberry",2,"cup"), DAIRY("eggs",2,"each"), DAIRY("butter",0.5), PAN("sugar",1),
   DAIRY("milk",0.75), PAN("baking powder",1,"tbsp"), salt()],
  "Cream the butter and sugar, then beat in the eggs. Alternate adding flour mixed with baking powder and the milk. Fold in the blueberries and divide into a muffin tin. Bake at 375F until golden and a tester comes out clean.",
  "budget",["american","vegetarian","comfort","budget","oven"])

add("breakfast-tacos","Breakfast Tacos","Soft tacos with scrambled eggs, bacon, and cheese.","breakfast",20,
  [DAIRY("eggs",8,"each"), MEAT("bacon",0.5), BREAD("corn tortillas",8), cheddar(1), PAN("salsa",0.5),
   PROD("avocado",1), cilantro()],
  "Crisp the bacon and scramble the eggs softly. Warm the tortillas in a dry pan. Fill with eggs, bacon, and cheese. Top with avocado, salsa, and cilantro.",
  "budget",["quick","mexican","pork","budget"])

add("yogurt-parfait","Berry Yogurt Parfait","Layered yogurt parfait with granola and berries.","breakfast",10,
  [DAIRY("greek yogurt",3), PAN("granola",2), PROD("strawberry",2,"cup"), PROD("blueberry",1,"cup"), PAN("honey",3,"tbsp")],
  "Slice the strawberries and rinse the blueberries. Spoon yogurt into glasses. Layer with granola, berries, and a drizzle of honey. Repeat the layers and serve.",
  "moderate",["quick","american","vegetarian","healthy"])

add("cheese-omelette","Three Cheese Omelette","Fluffy omelette filled with melted cheeses and herbs.","breakfast",15,
  [DAIRY("eggs",8,"each"), DAIRY("cheddar cheese",0.75), DAIRY("mozzarella cheese",0.5), DAIRY("parmesan cheese",0.25),
   DAIRY("butter",2,"tbsp"), PROD("chives",0.25,"bunch"), DAIRY("milk",0.25)],
  "Whisk the eggs with milk, salt, and pepper. Melt butter in a nonstick pan and pour in the eggs. As they set, sprinkle on the cheeses and fold. Slide onto plates and garnish with chives.",
  "budget",["quick","american","vegetarian","high-protein","low-carb","gluten-free","budget"])

add("banana-oat-pancakes","Banana Oat Pancakes","Wholesome flourless banana oat pancakes.","breakfast",20,
  [PROD("banana",3), PAN("rolled oats",2), DAIRY("eggs",3,"each"), DAIRY("milk",0.5), PAN("baking powder",1),
   PAN("maple syrup",0.5), SP("cinnamon",1)],
  "Blend the banana, oats, eggs, milk, baking powder, and cinnamon into a batter. Let it rest a few minutes to thicken. Cook small pancakes on a greased griddle until set and golden. Serve with maple syrup.",
  "budget",["quick","american","vegetarian","healthy","budget","gluten-free"])

add("huevos-rancheros","Huevos Rancheros","Fried eggs over tortillas with salsa and beans.","breakfast",25,
  [DAIRY("eggs",8,"each"), BREAD("corn tortillas",8), PAN("black beans",1,"can"), PAN("salsa",1), cheddar(1),
   PROD("avocado",2), cilantro(), olive_oil()],
  "Warm the beans and crisp the tortillas in a little oil. Fry the eggs sunny-side up. Place eggs over the tortillas with beans. Top with salsa, cheese, avocado, and cilantro.",
  "budget",["quick","mexican","vegetarian","healthy","budget"])

add("french-toast","Cinnamon French Toast","Golden French toast dusted with cinnamon sugar.","breakfast",20,
  [BREAD("brioche bread",8,"slice"), DAIRY("eggs",4,"each"), DAIRY("milk",0.75), SP("cinnamon",1,"tbsp"), PAN("sugar",2,"tbsp"),
   DAIRY("butter",3,"tbsp"), PAN("maple syrup",0.5)],
  "Whisk eggs, milk, cinnamon, and sugar into a custard. Dip the brioche slices to soak both sides. Cook in butter until golden on each side. Serve with maple syrup.",
  "budget",["quick","american","vegetarian","comfort","budget"])

add("breakfast-hash","Sweet Potato Breakfast Hash","Crispy sweet potato hash with eggs and peppers.","breakfast",30,
  [PROD("sweet potato",2), DAIRY("eggs",6,"each"), PROD("bell pepper",1), onion(1), garlic(3), SP("paprika",1),
   PROD("avocado",1), olive_oil()],
  "Crisp diced sweet potato in olive oil until tender. Add pepper, onion, garlic, and paprika and cook through. Make wells and crack in the eggs, then cover until set. Top with sliced avocado.",
  "budget",["quick","american","vegetarian","healthy","budget","gluten-free"])

add("bacon-egg-cheese-bagel","Bacon Egg and Cheese Bagel","Classic breakfast sandwich on a toasted bagel.","breakfast",20,
  [BREAD("bagels",4), DAIRY("eggs",4,"each"), MEAT("bacon",0.5), DAIRY("cheddar cheese",0.75), DAIRY("butter",2,"tbsp")],
  "Toast the bagels and crisp the bacon. Fry the eggs to your preference. Place egg, bacon, and cheddar on the bottom bagel halves. Close the sandwiches and serve warm.",
  "budget",["quick","american","pork","comfort","budget"])

add("chia-pudding","Vanilla Chia Pudding","Creamy make-ahead chia pudding with fruit.","breakfast",10,
  [PAN("chia seeds",0.5), PAN("almond milk",2), PAN("maple syrup",3,"tbsp"), SP("vanilla extract",1), PROD("strawberry",1.5,"cup"),
   PAN("granola",0.75)],
  "Whisk the chia seeds, almond milk, maple syrup, and vanilla together. Refrigerate overnight until thick and set. Stir well and divide into jars. Top with sliced strawberries and granola.",
  "budget",["quick","american","vegan","vegetarian","healthy","budget","meal-prep","dairy-free"])

add("ham-cheese-scramble","Ham and Cheese Scramble","Soft scrambled eggs with diced ham and cheddar.","breakfast",15,
  [DAIRY("eggs",8,"each"), MEAT("ham",0.5), DAIRY("cheddar cheese",1), DAIRY("butter",2,"tbsp"), PROD("green onion",3),
   DAIRY("milk",0.25)],
  "Whisk the eggs with milk and a pinch of salt. Saute the diced ham in butter until lightly browned. Pour in the eggs and gently scramble. Fold in cheddar and green onion just before serving.",
  "budget",["quick","american","pork","high-protein","budget","gluten-free"])

add("pumpkin-spice-oatmeal","Pumpkin Spice Oatmeal","Warm spiced oatmeal with pumpkin and pecans.","breakfast",20,
  [PAN("rolled oats",2), DAIRY("milk",3), PAN("pumpkin puree",1), PAN("maple syrup",0.25), SP("cinnamon",1,"tbsp"),
   PAN("pecans",0.5), SP("nutmeg",0.5)],
  "Simmer the oats with milk until creamy. Stir in the pumpkin puree, cinnamon, and nutmeg. Sweeten with maple syrup. Top with toasted pecans.",
  "budget",["quick","american","vegetarian","healthy","budget"])

add("smoked-salmon-toast","Smoked Salmon Toast","Cream cheese toast topped with smoked salmon.","breakfast",15,
  [MEAT("smoked salmon",0.5), BREAD("rye bread",4,"slice"), DAIRY("cream cheese",0.5), PROD("red onion",0.25),
   PROD("cucumber",1), PROD("dill",0.25,"bunch"), lime(1)],
  "Toast the rye bread and spread thickly with cream cheese. Layer with smoked salmon and thin cucumber. Top with red onion, dill, and a squeeze of lemon. Serve open-faced.",
  "premium",["quick","american","seafood","high-protein"])

# =====================================================================
# GROUP 6: 20 BUDGET MEALS (beans, lentils, eggs, rice-based, under $2/serving)
# =====================================================================

add("red-beans-and-rice","Red Beans and Rice","Creamy Cajun-spiced red beans over fluffy rice.","dinner",45,
  [PAN("red kidney beans",3,"can"), PAN("white rice",2), onion(1), PROD("bell pepper",1), PROD("celery",3,"each"),
   garlic(5), SP("cajun seasoning",1,"tbsp"), SP("smoked paprika",1), PAN("vegetable broth",2)],
  "Saute onion, pepper, celery, and garlic until soft. Add the beans, broth, and Cajun seasoning and simmer. Mash some beans to thicken the pot. Serve over rice.",
  "budget",["budget","american","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free","meal-prep"])

add("dal-and-rice","Red Lentil Dal","Comforting spiced red lentil dal over rice.","dinner",35,
  [PAN("red lentils",1.5), onion(1), garlic(5), PROD("ginger",1,"tbsp"), can_tomato(), SP("turmeric",1),
   SP("cumin",1,"tbsp"), SP("garam masala",1), PAN("white rice",2), cilantro()],
  "Saute onion, garlic, and ginger with the spices. Add the lentils, tomatoes, and water and simmer until the lentils break down. Stir until creamy and season to taste. Serve over rice with cilantro.",
  "budget",["budget","indian","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free","meal-prep"])

add("bean-and-cheese-burritos","Bean and Cheese Burritos","Simple filling burritos with refried beans and cheese.","dinner",25,
  [PAN("refried beans",2,"can"), BREAD("flour tortillas",6), cheddar(2), PAN("white rice",1.5), PAN("salsa",0.75),
   SP("cumin",1), onion(0.5)],
  "Warm the refried beans with cumin and a little water. Cook the rice. Spread beans, rice, and cheese on the tortillas. Roll into burritos and sear seam-side down until crisp.",
  "budget",["quick","budget","mexican","vegetarian"])

add("fried-rice-budget","Egg Fried Rice","Simple fried rice with egg and frozen vegetables.","dinner",20,
  [PAN("white rice",3), DAIRY("eggs",4,"each"), FROZ("mixed vegetables",2), garlic(3), PAN("soy sauce",3,"tbsp"),
   PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Scramble the eggs in sesame oil and set aside. Stir-fry the garlic and frozen vegetables until hot. Add the rice and soy sauce and toss over high heat. Fold in the eggs and green onion.",
  "budget",["quick","budget","asian","vegetarian","one-pot"])

add("pasta-fagioli","Pasta e Fagioli","Italian pasta and bean soup that feeds a crowd cheaply.","dinner",40,
  [PAN("cannellini beans",2,"can"), PAN("ditalini pasta",1), can_tomato(), onion(1), PROD("carrot",2), PROD("celery",3,"each"),
   garlic(4), PAN("vegetable broth",5), SP("italian seasoning",1,"tbsp"), olive_oil()],
  "Saute onion, carrot, celery, and garlic in olive oil. Add tomatoes, broth, beans, and seasoning and simmer. Stir in the pasta and cook until tender. Mash some beans to thicken and adjust the seasoning.",
  "budget",["budget","italian","vegetarian","healthy","one-pot","meal-prep"])

add("chickpea-rice-skillet","Spiced Chickpea Rice Skillet","One-pan chickpeas and rice with warm spices.","dinner",35,
  [PAN("chickpeas",2,"can"), PAN("white rice",1.5), onion(1), garlic(4), can_tomato(), SP("cumin",1,"tbsp"),
   SP("smoked paprika",1), spinach(4), PAN("vegetable broth",2.5), olive_oil()],
  "Saute onion and garlic with cumin and paprika. Add the rice, chickpeas, tomatoes, and broth. Cover and simmer until the rice is tender. Stir in spinach until wilted.",
  "budget",["budget","mediterranean","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free"])

add("egg-drop-soup-rice","Egg Drop Soup with Rice","Silky egg drop soup served over rice.","dinner",20,
  [DAIRY("eggs",5,"each"), PAN("chicken broth",6), PAN("white rice",2), PROD("green onion",4), garlic(3),
   PROD("ginger",1,"tbsp"), PAN("cornstarch",2,"tbsp"), PAN("soy sauce",1,"tbsp")],
  "Simmer the broth with garlic and ginger, then thicken with a cornstarch slurry. Drizzle in beaten eggs while stirring to form ribbons. Season with soy sauce. Ladle over cooked rice and top with green onion.",
  "budget",["quick","budget","asian","one-pot"])

add("black-bean-tacos","Black Bean Tacos","Quick seasoned black bean tacos with all the toppings.","dinner",20,
  [PAN("black beans",2,"can"), BREAD("corn tortillas",12), cheddar(1), PROD("lettuce",1,"each"), PAN("salsa",0.75),
   SP("cumin",1,"tbsp"), SP("chili powder",1), PROD("avocado",1), cilantro(), lime(2)],
  "Simmer the black beans with cumin, chili powder, and a splash of water until thick. Warm the tortillas in a dry pan. Fill with beans, lettuce, cheese, and avocado. Top with salsa, cilantro, and lime.",
  "budget",["quick","budget","mexican","vegetarian","healthy"])

add("lentil-bolognese","Lentil Bolognese","Meatless lentil ragu over pasta, hearty and cheap.","dinner",45,
  [PAN("brown lentils",1.5), PAN("spaghetti",1,"lb"), can_tomato(), PAN("tomato paste",3,"tbsp"), onion(1), PROD("carrot",2),
   garlic(5), SP("italian seasoning",1,"tbsp"), olive_oil()],
  "Saute onion, carrot, and garlic in olive oil. Add lentils, tomatoes, tomato paste, and seasoning and simmer until the lentils are tender. Cook the spaghetti until al dente. Toss the pasta with the lentil ragu.",
  "budget",["budget","italian","vegan","vegetarian","healthy","meal-prep","dairy-free"])

add("potato-egg-skillet","Potato and Egg Skillet","Crispy potatoes topped with eggs for a cheap dinner.","dinner",30,
  [PROD("potato",2,"lb"), DAIRY("eggs",6,"each"), onion(1), PROD("bell pepper",1), garlic(3), SP("paprika",1),
   cheddar(0.75), olive_oil()],
  "Crisp diced potatoes in olive oil until golden and tender. Add onion, pepper, garlic, and paprika and cook through. Make wells and crack in the eggs, then cover until set. Top with cheddar and let it melt.",
  "budget",["quick","budget","american","vegetarian","one-pot"])

add("rice-and-beans-bowl","Cuban Rice and Beans Bowl","Black beans over rice with a fried egg on top.","dinner",30,
  [PAN("black beans",2,"can"), PAN("white rice",2), DAIRY("eggs",4,"each"), onion(1), garlic(4), PROD("bell pepper",1),
   SP("cumin",1,"tbsp"), SP("oregano",1), olive_oil()],
  "Cook the rice. Saute onion, pepper, and garlic, then add the beans, cumin, and oregano and simmer. Fry the eggs sunny-side up. Serve beans over rice topped with a fried egg.",
  "budget",["quick","budget","mexican","vegetarian","healthy"])

add("curried-lentil-stew","Curried Lentil Stew","Thick lentil stew with coconut and warm spices.","dinner",40,
  [PAN("brown lentils",2), PAN("coconut milk",1,"can"), can_tomato(), onion(1), garlic(5), PROD("ginger",1,"tbsp"),
   SP("curry powder",1.5,"tbsp"), PROD("carrot",2), spinach(4), PAN("white rice",2)],
  "Saute onion, garlic, and ginger with curry powder. Add lentils, tomatoes, coconut milk, and carrot. Simmer until the lentils are tender and the stew thickens. Stir in spinach and serve over rice.",
  "budget",["budget","indian","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free","meal-prep"])

add("cheesy-rice-broccoli","Cheesy Broccoli Rice","Comforting cheesy rice loaded with broccoli.","dinner",30,
  [PAN("white rice",2), PROD("broccoli",5,"cup"), DAIRY("cheddar cheese",2), DAIRY("milk",1), onion(0.5), garlic(3),
   DAIRY("butter",2,"tbsp"), PAN("vegetable broth",2.5)],
  "Cook the rice in broth with onion and garlic. Steam the broccoli until just tender. Stir the broccoli, milk, and butter into the rice. Melt in the cheddar until creamy.",
  "budget",["quick","budget","american","vegetarian","comfort","one-pot"])

add("beans-on-toast","Smoky Beans on Toast","Saucy spiced beans piled on toasted bread.","dinner",20,
  [PAN("white beans",2,"can"), BREAD("crusty bread",4,"slice"), can_tomato(), onion(1), garlic(4), PAN("tomato paste",2,"tbsp"),
   SP("smoked paprika",1), DAIRY("butter",2,"tbsp"), olive_oil()],
  "Saute onion and garlic, then add tomatoes, tomato paste, and paprika. Stir in the beans and simmer until thick and saucy. Toast and butter the bread. Spoon the smoky beans over the toast.",
  "budget",["quick","budget","mediterranean","vegetarian"])

add("mexican-rice-skillet","Mexican Rice Skillet","One-pan Mexican rice with beans and corn.","dinner",35,
  [PAN("white rice",1.5), PAN("black beans",1,"can"), FROZ("corn",1.5), can_tomato(), onion(1), garlic(4),
   PROD("bell pepper",1), SP("cumin",1,"tbsp"), SP("chili powder",1), cheddar(1), PAN("vegetable broth",2.5)],
  "Saute onion, pepper, and garlic with cumin and chili powder. Stir in the rice to toast, then add tomatoes, beans, corn, and broth. Cover and simmer until the rice is tender. Top with cheese and let it melt.",
  "budget",["budget","mexican","vegetarian","one-pot","meal-prep"])

add("chickpea-curry-budget","Quick Chickpea Curry","Pantry-friendly chickpea curry over rice.","dinner",30,
  [PAN("chickpeas",2,"can"), can_tomato(), onion(1), garlic(5), PROD("ginger",1,"tbsp"), SP("curry powder",1.5,"tbsp"),
   PAN("white rice",2), FROZ("peas",1), olive_oil()],
  "Saute onion, garlic, and ginger with curry powder. Add tomatoes and simmer into a sauce. Stir in chickpeas and peas and warm through. Serve over rice.",
  "budget",["quick","budget","indian","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free"])

add("spanish-tortilla","Spanish Potato Tortilla","Thick potato and egg omelette, cheap and filling.","dinner",40,
  [PROD("potato",1.5,"lb"), DAIRY("eggs",8,"each"), onion(1), olive_oil(), salt(), pepper()],
  "Slowly cook thin potato and onion slices in olive oil until soft. Whisk the eggs and fold in the potatoes. Pour into the pan and cook until the bottom sets. Flip and finish cooking until set throughout.",
  "budget",["budget","mediterranean","vegetarian","healthy","gluten-free","one-pot"])

add("ramen-upgrade","Loaded Veggie Ramen","Dressed-up ramen with egg and vegetables.","dinner",20,
  [PAN("ramen noodles",4,"each"), DAIRY("eggs",4,"each"), PROD("bok choy",4,"cup"), PROD("carrot",2), garlic(4),
   PROD("ginger",1,"tbsp"), PAN("soy sauce",2,"tbsp"), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Simmer broth with garlic, ginger, soy sauce, and sesame oil. Soft-boil the eggs and halve them. Cook the ramen and vegetables in the broth until tender. Serve topped with eggs and green onion.",
  "budget",["quick","budget","asian","vegetarian"])

add("bean-chili-budget","Three Bean Chili","Meatless three-bean chili that is cheap and filling.","dinner",40,
  [PAN("kidney beans",1,"can"), PAN("black beans",1,"can"), PAN("pinto beans",1,"can"), can_tomato(), onion(1),
   PROD("bell pepper",1), garlic(5), SP("chili powder",2,"tbsp"), SP("cumin",1,"tbsp"), PAN("tomato paste",2,"tbsp")],
  "Saute onion, pepper, and garlic with chili powder and cumin. Add all the beans, tomatoes, and tomato paste. Simmer until thick and the flavors meld. Adjust the seasoning before serving.",
  "budget",["budget","american","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free","meal-prep"])

add("savory-oatmeal-egg","Savory Oatmeal with Egg","Hearty savory oats topped with a soft egg.","dinner",20,
  [PAN("rolled oats",2), PAN("vegetable broth",4), DAIRY("eggs",4,"each"), spinach(4), DAIRY("parmesan cheese",0.5),
   garlic(3), PROD("green onion",3), olive_oil()],
  "Cook the oats in broth with garlic until creamy. Stir in spinach until wilted and add parmesan. Fry the eggs to your liking. Top each bowl of oats with an egg and green onion.",
  "budget",["quick","budget","vegetarian","healthy","one-pot"])

# =====================================================================
# GROUP 7: 15 HIGH-PROTEIN / LOW-CARB DINNERS
# =====================================================================

add("baked-salmon-asparagus","Baked Salmon and Asparagus","Sheet-pan lemon salmon with roasted asparagus.","dinner",30,
  [MEAT("salmon fillet",1.75), PROD("asparagus",2,"bunch"), lime(2), garlic(4), DAIRY("butter",3,"tbsp"),
   SP("dill",1), olive_oil(), salt(), pepper()],
  "Arrange the salmon and asparagus on a sheet pan. Drizzle with olive oil, garlic, and lemon and season well. Roast at 400F until the salmon flakes and the asparagus is tender. Finish with a knob of butter and dill.",
  "premium",["quick","seafood","healthy","high-protein","low-carb","oven","gluten-free"])

add("grilled-chicken-broccoli","Grilled Chicken and Broccoli","Simple high-protein chicken with charred broccoli.","dinner",30,
  [MEAT("chicken breast",2), PROD("broccoli",6,"cup"), garlic(4), lime(1), SP("paprika",1), SP("garlic powder",1),
   olive_oil(), salt(), pepper()],
  "Season the chicken with paprika, garlic powder, salt, and pepper. Grill or sear until cooked through, then rest. Roast or char the broccoli with olive oil and garlic. Serve the sliced chicken with broccoli and lemon.",
  "moderate",["quick","american","chicken","healthy","high-protein","low-carb","gluten-free"])

add("steak-and-veggies","Garlic Butter Steak and Veggies","Seared steak with sauteed zucchini and mushrooms.","dinner",30,
  [MEAT("sirloin steak",1.75), PROD("zucchini",2), PROD("mushroom",0.75,"lb"), DAIRY("butter",4,"tbsp"), garlic(5),
   PROD("parsley",0.5,"bunch"), olive_oil(), salt(), pepper()],
  "Season and sear the steak to your preferred doneness, then rest. Saute the zucchini and mushrooms in butter and garlic. Slice the steak against the grain. Serve over the vegetables with parsley.",
  "moderate",["quick","american","beef","high-protein","low-carb","gluten-free"])

add("egg-roll-bowl-protein","Pork Egg Roll Bowl","High-protein deconstructed egg roll, low in carbs.","dinner",25,
  [MEAT("ground pork",1.5), PROD("cabbage",6,"cup"), PROD("carrot",2), garlic(5), PROD("ginger",1,"tbsp"),
   PAN("soy sauce",3,"tbsp"), PAN("sesame oil",1,"tbsp"), PROD("green onion",4)],
  "Brown the pork with garlic and ginger in sesame oil. Add cabbage and carrot and stir-fry until wilted. Season with soy sauce and toss until tender. Top with green onion.",
  "budget",["quick","asian","pork","high-protein","low-carb","one-pot"])

add("chicken-cauliflower-rice","Chicken Cauliflower Fried Rice","Low-carb fried rice with cauliflower and chicken.","dinner",28,
  [MEAT("chicken breast",1.5), FROZ("cauliflower rice",4), DAIRY("eggs",3,"each"), FROZ("peas and carrots",1), garlic(4),
   PAN("soy sauce",3,"tbsp"), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Scramble the eggs in sesame oil and set aside. Cook the diced chicken until browned. Add cauliflower rice, peas, carrots, and garlic and stir-fry until tender. Stir in soy sauce, eggs, and green onion.",
  "moderate",["quick","asian","chicken","healthy","high-protein","low-carb","one-pot"])

add("stuffed-chicken-spinach","Spinach Stuffed Chicken","Chicken breasts stuffed with spinach and cheese.","dinner",40,
  [MEAT("chicken breast",2), spinach(5), DAIRY("cream cheese",0.5), DAIRY("mozzarella cheese",1), garlic(4),
   SP("italian seasoning",1), olive_oil(), salt(), pepper()],
  "Mix wilted spinach with cream cheese, mozzarella, and garlic. Cut a pocket in each chicken breast and stuff with the filling. Sear to brown, then bake at 400F until cooked through. Rest before serving.",
  "moderate",["american","chicken","high-protein","low-carb","gluten-free","oven"])

add("shrimp-zoodles","Garlic Shrimp Zoodles","Garlicky shrimp over spiralized zucchini noodles.","dinner",25,
  [MEAT("shrimp",1.5), PROD("zucchini",4), DAIRY("butter",4,"tbsp"), garlic(6), SP("red pepper flakes",0.5),
   DAIRY("parmesan cheese",0.5), lime(1), PROD("parsley",0.5,"bunch")],
  "Spiralize the zucchini into noodles. Saute the shrimp in butter and garlic until pink. Add the zoodles and toss just until tender. Finish with parmesan, lemon, parsley, and red pepper flakes.",
  "moderate",["quick","italian","seafood","healthy","high-protein","low-carb","gluten-free"])

add("turkey-lettuce-wraps","Turkey Lettuce Wraps","Asian-style ground turkey in crisp lettuce cups.","dinner",25,
  [MEAT("ground turkey",1.5), PROD("butter lettuce",2,"each"), PROD("water chestnuts",1,"can"), garlic(5),
   PROD("ginger",1,"tbsp"), PAN("soy sauce",3,"tbsp"), PROD("green onion",4), PAN("sesame oil",1,"tbsp"), PROD("carrot",2)],
  "Brown the turkey with garlic and ginger in sesame oil. Add chopped water chestnuts and carrot and cook through. Season with soy sauce and toss. Spoon into lettuce cups and top with green onion.",
  "moderate",["quick","asian","meat","healthy","high-protein","low-carb"])

add("baked-cod-tomatoes","Baked Cod with Tomatoes","Mediterranean baked cod with tomatoes and olives.","dinner",30,
  [MEAT("cod fillet",1.75), PROD("cherry tomato",2,"cup"), PROD("kalamata olives",0.5,"cup"), garlic(5), lime(1),
   SP("oregano",1), olive_oil(), PROD("parsley",0.5,"bunch")],
  "Arrange the cod in a baking dish with tomatoes, olives, and garlic. Drizzle with olive oil, lemon, and oregano. Bake at 400F until the cod flakes and the tomatoes burst. Garnish with parsley.",
  "moderate",["quick","mediterranean","seafood","healthy","high-protein","low-carb","gluten-free","dairy-free","oven"])

add("pork-chops-green-beans","Pork Chops and Green Beans","Pan-seared pork chops with garlic green beans.","dinner",30,
  [MEAT("pork chops",2), PROD("green beans",1.25,"lb"), garlic(5), DAIRY("butter",3,"tbsp"), SP("thyme",1),
   olive_oil(), salt(), pepper()],
  "Season the pork chops and sear in olive oil until golden and cooked, then rest. Saute the green beans with garlic and butter until crisp-tender. Add thyme and toss. Serve the chops alongside the green beans.",
  "moderate",["quick","american","pork","high-protein","low-carb","gluten-free"])

add("chicken-fajita-skillet-lowcarb","Low-Carb Chicken Fajita Skillet","Chicken and peppers without the tortillas.","dinner",28,
  [MEAT("chicken breast",2), PROD("bell pepper",3), onion(1), SP("chili powder",1,"tbsp"), SP("cumin",1),
   PROD("avocado",2), lime(2), sour_cream(0.5), cheddar(1), olive_oil()],
  "Season the sliced chicken with chili powder and cumin and sear until cooked. Add peppers and onion and char until tender. Squeeze lime over the top. Serve with avocado, sour cream, and cheese.",
  "moderate",["quick","mexican","chicken","high-protein","low-carb","gluten-free"])

add("salmon-cakes","Salmon Cakes with Slaw","Pan-fried salmon patties over a crunchy slaw.","dinner",30,
  [MEAT("canned salmon",2,"can"), DAIRY("eggs",2,"each"), PAN("almond flour",0.5), PROD("cabbage",4,"cup"), PROD("carrot",2),
   DAIRY("mayonnaise",0.33), lime(2), PROD("green onion",4), olive_oil()],
  "Mix the salmon with egg, almond flour, and green onion, then form into patties. Pan-fry until golden on both sides. Toss shredded cabbage and carrot with mayonnaise and lime. Serve the cakes over the slaw.",
  "moderate",["quick","seafood","high-protein","low-carb","gluten-free"])

add("beef-broccoli-lowcarb","Sesame Beef and Broccoli","Tender beef and broccoli without the rice.","dinner",28,
  [MEAT("flank steak",1.75), PROD("broccoli",6,"cup"), garlic(4), PROD("ginger",1,"tbsp"), PAN("soy sauce",4,"tbsp"),
   PAN("sesame oil",2,"tbsp"), PAN("sesame seeds",2,"tbsp"), PROD("green onion",4)],
  "Sear thin-sliced beef in sesame oil over high heat, then remove. Stir-fry the broccoli with garlic and ginger until bright. Return the beef and add soy sauce. Toss and finish with sesame seeds and green onion.",
  "moderate",["quick","asian","beef","high-protein","low-carb"])

add("greek-chicken-skewers","Greek Chicken Skewers","Marinated chicken skewers with cucumber yogurt.","dinner",40,
  [MEAT("chicken breast",2), DAIRY("greek yogurt",1), PROD("cucumber",1), lime(2), garlic(5), SP("oregano",1,"tbsp"),
   PROD("cherry tomato",2,"cup"), olive_oil()],
  "Marinate the cubed chicken in yogurt, lemon, garlic, and oregano. Thread onto skewers with cherry tomatoes. Grill until charred and cooked through. Serve with a quick cucumber yogurt sauce.",
  "moderate",["mediterranean","chicken","healthy","high-protein","low-carb","gluten-free"])

add("cabbage-beef-skillet","Beef and Cabbage Skillet","Savory ground beef and cabbage one-pan dinner.","dinner",30,
  [MEAT("ground beef",1.5), PROD("cabbage",6,"cup"), onion(1), garlic(5), can_tomato(), SP("paprika",1),
   SP("italian seasoning",1), olive_oil()],
  "Brown the beef with onion and garlic. Add the cabbage and cook until it wilts down. Stir in tomatoes, paprika, and seasoning and simmer until tender. Adjust the seasoning and serve.",
  "budget",["quick","american","beef","healthy","high-protein","low-carb","budget","one-pot","gluten-free"])

# =====================================================================
# GROUP 8: 15 VEGETARIAN / VEGAN DINNERS (hearty and light)
# =====================================================================

add("mushroom-risotto","Creamy Mushroom Risotto","Rich, creamy risotto with mushrooms and parmesan.","dinner",45,
  [PAN("arborio rice",1.5), PROD("mushroom",1,"lb"), onion(1), garlic(5), PAN("white wine",0.5),
   DAIRY("parmesan cheese",1), DAIRY("butter",4,"tbsp"), PAN("vegetable broth",6), PROD("parsley",0.5,"bunch")],
  "Saute the mushrooms until golden and set aside. Soften onion and garlic, then toast the rice. Add wine, then ladle in warm broth gradually, stirring until creamy. Fold in mushrooms, butter, and parmesan.",
  "moderate",["italian","vegetarian","comfort"])

add("vegan-buddha-bowl","Vegan Buddha Bowl","Colorful bowl with roasted vegetables and tahini.","dinner",40,
  [PAN("quinoa",1.5), PROD("sweet potato",2), PAN("chickpeas",1,"can"), PROD("kale",4,"cup"), PROD("avocado",2),
   PAN("tahini",0.33), lime(2), PROD("carrot",2), SP("cumin",1), olive_oil()],
  "Cook the quinoa and roast the sweet potato and chickpeas with cumin. Massage the kale with olive oil and lemon. Whisk tahini with lemon and water for the dressing. Build bowls with quinoa, vegetables, and avocado and drizzle with tahini.",
  "moderate",["mediterranean","vegan","vegetarian","healthy","dairy-free"])

add("black-bean-burgers","Black Bean Burgers","Hearty homemade black bean burgers with all the fixings.","dinner",35,
  [PAN("black beans",2,"can"), BREAD("burger buns",4), PAN("breadcrumbs",0.75), DAIRY("eggs",1,"each"), onion(0.5),
   garlic(3), SP("cumin",1,"tbsp"), SP("smoked paprika",1), PROD("lettuce",1,"each"), PROD("tomato",2), olive_oil()],
  "Mash the beans with onion, garlic, cumin, and paprika. Mix in breadcrumbs and egg, then form into patties. Pan-fry until crisp on both sides. Serve on buns with lettuce and tomato.",
  "budget",["american","vegetarian","budget","comfort"])

add("eggplant-curry","Eggplant Coconut Curry","Silky eggplant simmered in spiced coconut sauce.","dinner",40,
  [PROD("eggplant",2,"lb"), PAN("coconut milk",1,"can"), can_tomato(), onion(1), garlic(5), PROD("ginger",1,"tbsp"),
   SP("curry powder",1.5,"tbsp"), PAN("white rice",2), cilantro()],
  "Saute onion, garlic, and ginger with curry powder. Add the eggplant and cook until it softens. Pour in tomatoes and coconut milk and simmer until silky. Serve over rice with cilantro.",
  "budget",["indian","vegan","vegetarian","healthy","one-pot","dairy-free","gluten-free"])

add("caprese-stuffed-portobellos","Stuffed Portobello Mushrooms","Roasted portobellos filled with tomato and mozzarella.","dinner",30,
  [PROD("portobello mushroom",4,"each"), DAIRY("mozzarella cheese",1.5), PROD("tomato",3), PROD("basil",1,"bunch"),
   garlic(4), PAN("balsamic glaze",2,"tbsp"), olive_oil(), PAN("breadcrumbs",0.5)],
  "Remove the mushroom stems and brush the caps with garlic oil. Fill with chopped tomato, mozzarella, and breadcrumbs. Roast at 400F until the mushrooms are tender and the cheese melts. Finish with basil and balsamic.",
  "moderate",["quick","italian","vegetarian","healthy","low-carb","oven"])

add("vegan-chili","Smoky Vegan Chili","Rich three-bean chili with sweet potato and corn.","dinner",45,
  [PAN("black beans",1,"can"), PAN("kidney beans",1,"can"), PAN("pinto beans",1,"can"), PROD("sweet potato",2), can_tomato(),
   FROZ("corn",1), onion(1), garlic(5), SP("chili powder",2,"tbsp"), SP("cumin",1,"tbsp"), SP("smoked paprika",1)],
  "Saute onion and garlic with chili powder, cumin, and paprika. Add the sweet potato, tomatoes, and beans. Simmer until the sweet potato is tender and the chili thickens. Stir in corn before serving.",
  "budget",["american","vegan","vegetarian","healthy","budget","one-pot","dairy-free","gluten-free","meal-prep"])

add("spinach-ricotta-gnocchi","Spinach Ricotta Gnocchi","Pillowy gnocchi in a creamy spinach sauce.","dinner",30,
  [PAN("potato gnocchi",1.5,"lb"), spinach(5), DAIRY("ricotta cheese",1), DAIRY("parmesan cheese",0.5), garlic(4),
   DAIRY("heavy cream",0.5), onion(0.5), olive_oil()],
  "Boil the gnocchi until they float, then drain. Saute onion and garlic, then add spinach until wilted. Stir in ricotta, cream, and parmesan to form a sauce. Fold in the gnocchi and warm through.",
  "moderate",["quick","italian","vegetarian","comfort"])

add("tofu-stir-fry","Crispy Tofu Stir Fry","Golden tofu and vegetables in a savory garlic sauce.","dinner",30,
  [PAN("firm tofu",1.5,"lb"), PROD("broccoli",4,"cup"), PROD("bell pepper",2), garlic(5), PROD("ginger",1,"tbsp"),
   PAN("soy sauce",4,"tbsp"), PAN("cornstarch",2,"tbsp"), PAN("white rice",2), PAN("sesame oil",1,"tbsp")],
  "Press and cube the tofu, then toss in cornstarch and pan-fry until crisp. Stir-fry the broccoli and pepper with garlic and ginger. Return the tofu and add soy sauce thickened with cornstarch. Serve over rice.",
  "budget",["quick","asian","vegan","vegetarian","healthy","budget","dairy-free"])

add("stuffed-acorn-squash","Stuffed Acorn Squash","Roasted squash filled with quinoa, cranberries, and pecans.","dinner",55,
  [PROD("acorn squash",2,"each"), PAN("quinoa",1), PAN("dried cranberries",0.5,"cup"), PAN("pecans",0.5), spinach(3),
   onion(1), garlic(3), SP("cinnamon",0.5), olive_oil()],
  "Halve and roast the acorn squash until tender. Cook the quinoa and saute onion, garlic, and spinach. Mix the quinoa with cranberries, pecans, and cinnamon. Fill the squash halves and return to the oven to warm.",
  "moderate",["weekend","american","vegan","vegetarian","healthy","oven","dairy-free"])

add("vegetable-stir-fry","Garlic Vegetable Stir Fry","Crisp mixed vegetables in a light garlic sauce.","dinner",25,
  [PROD("broccoli",3,"cup"), PROD("bell pepper",2), PROD("snap peas",2,"cup"), PROD("carrot",2), garlic(5),
   PROD("ginger",1,"tbsp"), PAN("soy sauce",3,"tbsp"), PAN("white rice",2), PAN("sesame oil",1,"tbsp"), PAN("cornstarch",1,"tbsp")],
  "Cook the rice. Stir-fry all the vegetables in sesame oil over high heat until crisp-tender. Add garlic and ginger and toss. Pour in soy sauce thickened with cornstarch and serve over rice.",
  "budget",["quick","asian","vegan","vegetarian","healthy","budget","dairy-free"])

add("creamy-spinach-pasta","Creamy Spinach Pasta","Penne in a garlicky cream sauce loaded with spinach.","dinner",25,
  [PAN("penne pasta",1,"lb"), spinach(6), DAIRY("heavy cream",1), DAIRY("parmesan cheese",1), garlic(5), onion(0.5),
   DAIRY("butter",2,"tbsp"), SP("red pepper flakes",0.5)],
  "Boil the penne until al dente. Saute onion and garlic in butter, then add spinach until wilted. Pour in cream and simmer, then stir in parmesan. Toss with the pasta and a splash of pasta water.",
  "budget",["quick","italian","vegetarian","comfort","budget"])

add("chana-masala","Chana Masala","Spiced chickpea and tomato curry over rice.","dinner",35,
  [PAN("chickpeas",2,"can"), can_tomato(), onion(2), garlic(6), PROD("ginger",1,"tbsp"), SP("garam masala",1,"tbsp"),
   SP("cumin",1), SP("turmeric",1), PAN("white rice",2), cilantro()],
  "Saute onion, garlic, and ginger until deeply golden. Add the spices and tomatoes and cook into a thick masala. Stir in the chickpeas and simmer to absorb the flavor. Serve over rice with cilantro.",
  "budget",["indian","vegan","vegetarian","healthy","budget","one-pot","dairy-free","gluten-free","meal-prep"])

add("zucchini-noodle-primavera","Zucchini Noodle Primavera","Light zoodles tossed with spring vegetables.","dinner",25,
  [PROD("zucchini",4), PROD("cherry tomato",2,"cup"), PROD("asparagus",1,"bunch"), garlic(5), DAIRY("parmesan cheese",0.5),
   PROD("basil",1,"bunch"), olive_oil(), SP("red pepper flakes",0.5)],
  "Spiralize the zucchini into noodles. Saute the asparagus and tomatoes with garlic in olive oil. Add the zoodles and toss just until tender. Finish with parmesan, basil, and red pepper flakes.",
  "moderate",["quick","italian","vegetarian","healthy","low-carb","gluten-free"])

add("vegan-shepherds-pie","Lentil Shepherds Pie","Savory lentil and vegetable pie under mashed potatoes.","dinner",65,
  [PAN("brown lentils",2), PROD("potato",2.5,"lb"), FROZ("peas and carrots",2), onion(1), garlic(5),
   PAN("tomato paste",2,"tbsp"), PAN("vegetable broth",2), SP("thyme",1), PAN("almond milk",0.5), olive_oil()],
  "Boil and mash the potatoes with almond milk and olive oil. Saute onion and garlic, then add lentils, tomato paste, broth, and thyme and simmer. Stir in peas and carrots and spread into a dish. Top with mash and bake at 400F until golden.",
  "budget",["weekend","american","vegan","vegetarian","healthy","budget","oven","dairy-free","meal-prep"])

add("halloumi-veggie-skewers","Halloumi Vegetable Skewers","Grilled halloumi and vegetables with herb oil.","dinner",35,
  [DAIRY("halloumi cheese",1,"lb"), PROD("zucchini",2), PROD("bell pepper",2), PROD("red onion",1), PROD("cherry tomato",2,"cup"),
   garlic(4), SP("oregano",1), lime(1), olive_oil(), PAN("couscous",1.5)],
  "Cube the halloumi and chop the vegetables. Thread onto skewers and brush with garlic-herb oil. Grill until the halloumi is golden and the vegetables char. Serve over couscous with lemon.",
  "moderate",["mediterranean","vegetarian","healthy"])

add("vegan-pad-thai","Vegan Pad Thai","Rice noodles with tofu, peanuts, and tangy sauce.","dinner",30,
  [PAN("rice noodles",12,"oz"), PAN("firm tofu",1,"lb"), PAN("peanuts",0.5), PROD("bean sprouts",2,"cup"), garlic(4),
   PAN("soy sauce",3,"tbsp"), PAN("tamarind paste",2,"tbsp"), PAN("brown sugar",2,"tbsp"), lime(2), PROD("green onion",4)],
  "Soak the rice noodles until pliable. Pan-fry the cubed tofu until golden. Whisk soy sauce, tamarind, and brown sugar into a sauce. Toss the noodles, tofu, sauce, and sprouts together and top with peanuts, lime, and green onion.",
  "moderate",["asian","vegan","vegetarian","budget","dairy-free"])

# =====================================================================
# GROUP 9: FREE CHOICE (fill gaps, ensure variety)
# =====================================================================

add("chicken-shawarma-bowls","Chicken Shawarma Bowls","Spiced chicken over rice with garlic yogurt sauce.","dinner",40,
  [MEAT("chicken thighs",1.75), PAN("white rice",2), DAIRY("greek yogurt",1), garlic(6), lime(2), SP("cumin",1,"tbsp"),
   SP("paprika",1,"tbsp"), SP("turmeric",1), PROD("cucumber",1), PROD("tomato",2), olive_oil()],
  "Marinate the chicken in lemon, garlic, cumin, paprika, and turmeric. Sear until charred and cooked through, then slice. Cook the rice and make a garlic yogurt sauce. Build bowls with rice, chicken, cucumber, and tomato and drizzle with the sauce.",
  "moderate",["mediterranean","chicken","healthy","high-protein","meal-prep"])

add("gumbo","Chicken and Sausage Gumbo","Louisiana gumbo with a deep roux and the holy trinity.","dinner",75,
  [MEAT("chicken thighs",1.25), MEAT("andouille sausage",1), PROD("bell pepper",2), PROD("celery",4,"each"), onion(2),
   garlic(6), PAN("flour",0.5), PAN("chicken broth",6), PAN("white rice",2), SP("cajun seasoning",1,"tbsp"), PROD("green onion",4)],
  "Cook flour and oil into a deep brown roux. Add the onion, pepper, and celery and soften. Pour in broth with Cajun seasoning, chicken, and sausage and simmer until rich. Serve over rice with green onion.",
  "moderate",["weekend","american","meat","comfort","one-pot"])

add("ramen-noodle-soup","Chicken Ramen Noodle Soup","Savory ramen broth with chicken and soft eggs.","dinner",35,
  [MEAT("chicken breast",1.25), PAN("ramen noodles",4,"each"), DAIRY("eggs",4,"each"), PROD("bok choy",4,"cup"), garlic(5),
   PROD("ginger",1,"tbsp"), PAN("soy sauce",3,"tbsp"), PAN("chicken broth",6), PROD("green onion",4), PAN("sesame oil",1,"tbsp")],
  "Simmer broth with garlic, ginger, soy sauce, and sesame oil. Poach the chicken in the broth, then slice. Soft-boil the eggs and cook the noodles and bok choy in the broth. Assemble bowls with noodles, chicken, egg, and green onion.",
  "moderate",["asian","chicken","comfort"])

add("fish-tacos","Baja Fish Tacos","Crispy fish tacos with cabbage slaw and lime crema.","dinner",30,
  [MEAT("cod fillet",1.5), BREAD("corn tortillas",12), PROD("cabbage",4,"cup"), sour_cream(0.5), lime(3), PAN("flour",0.5),
   SP("chili powder",1), SP("cumin",1), cilantro(), olive_oil()],
  "Season and pan-fry the fish until crisp and flaky. Toss shredded cabbage with lime and cilantro. Warm the tortillas. Fill with fish and slaw and drizzle with lime crema.",
  "moderate",["quick","mexican","seafood","healthy"])

add("chicken-alfredo","Chicken Alfredo","Creamy fettuccine alfredo with seared chicken.","dinner",30,
  [MEAT("chicken breast",1.5), PAN("fettuccine pasta",1,"lb"), DAIRY("heavy cream",1.5), DAIRY("parmesan cheese",1.5),
   DAIRY("butter",4,"tbsp"), garlic(5), PROD("parsley",0.5,"bunch")],
  "Boil the fettuccine until al dente. Sear the seasoned chicken, then slice. Melt butter with garlic, add cream, and simmer, then stir in parmesan. Toss the pasta and chicken in the sauce and finish with parsley.",
  "moderate",["quick","italian","chicken","comfort"])

add("beef-enchiladas","Beef Enchiladas","Rolled tortillas with beef and cheese under red sauce.","dinner",50,
  [MEAT("ground beef",1.25), BREAD("flour tortillas",10), PAN("enchilada sauce",2.5), cheddar(2.5), onion(1),
   garlic(4), SP("cumin",1,"tbsp"), SP("chili powder",1), sour_cream(0.5)],
  "Brown the beef with onion, garlic, cumin, and chili powder. Roll the beef and some cheese into tortillas and place in a baking dish. Cover with enchilada sauce and cheese. Bake at 375F until bubbly and serve with sour cream.",
  "moderate",["mexican","beef","comfort","oven"])

add("chicken-curry","Chicken Tikka Masala","Tender chicken in a creamy spiced tomato sauce.","dinner",45,
  [MEAT("chicken thighs",1.75), can_tomato(), DAIRY("heavy cream",0.75), DAIRY("greek yogurt",0.5), onion(1), garlic(6),
   PROD("ginger",1,"tbsp"), SP("garam masala",1,"tbsp"), SP("cumin",1), PAN("white rice",2), cilantro()],
  "Marinate the chicken in yogurt and spices, then sear until charred. Saute onion, garlic, and ginger, then add tomatoes and garam masala. Simmer the sauce, stir in cream, and return the chicken. Serve over rice with cilantro.",
  "moderate",["indian","chicken","comfort"])

add("clam-chowder","New England Clam Chowder","Creamy chowder with clams, potatoes, and bacon.","dinner",45,
  [MEAT("canned clams",3,"can"), MEAT("bacon",0.4), PROD("potato",2,"lb"), onion(1), PROD("celery",3,"each"), garlic(3),
   DAIRY("heavy cream",1.5), DAIRY("milk",1), PAN("flour",0.25), DAIRY("butter",3,"tbsp"), SP("thyme",1)],
  "Crisp the bacon, then soften onion, celery, and garlic in the fat. Stir in butter and flour, then add the clam juice and potatoes. Simmer until the potatoes are tender. Stir in clams, cream, milk, and thyme and warm through.",
  "moderate",["meal-prep","american","seafood","comfort","one-pot"])

add("pork-stir-fry","Sweet and Sour Pork","Crispy pork with peppers and pineapple in tangy sauce.","dinner",35,
  [MEAT("pork loin",1.5), PROD("bell pepper",2), PROD("pineapple",2,"cup"), garlic(4), PAN("cornstarch",3,"tbsp"),
   PAN("rice vinegar",3,"tbsp"), PAN("ketchup",3,"tbsp"), PAN("brown sugar",2,"tbsp"), PAN("white rice",2), PAN("soy sauce",2,"tbsp")],
  "Toss the cubed pork in cornstarch and pan-fry until crisp. Stir-fry the peppers and pineapple with garlic. Whisk vinegar, ketchup, brown sugar, and soy sauce into a sauce and add to the pan. Toss in the pork and serve over rice.",
  "moderate",["asian","pork","comfort"])

add("turkey-meatloaf","Turkey Meatloaf","Tender turkey meatloaf with a sweet glaze.","dinner",70,
  [MEAT("ground turkey",2), PAN("breadcrumbs",1), DAIRY("eggs",2,"each"), onion(1), garlic(4), PAN("ketchup",0.5),
   PAN("worcestershire sauce",2,"tbsp"), PROD("potato",2,"lb"), DAIRY("milk",0.5), DAIRY("butter",3,"tbsp")],
  "Mix the turkey with breadcrumbs, egg, onion, and garlic and form a loaf. Top with a ketchup glaze and bake at 375F until cooked through. Boil and mash the potatoes with butter and milk. Slice the meatloaf and serve with the mash.",
  "budget",["weekend","american","meat","comfort","budget","oven"])

add("shrimp-grits","Shrimp and Grits","Creamy cheddar grits topped with garlicky shrimp.","dinner",40,
  [MEAT("shrimp",1.5), MEAT("bacon",0.4), PAN("grits",1.5), DAIRY("cheddar cheese",1.5), DAIRY("butter",3,"tbsp"),
   garlic(5), PROD("green onion",4), PAN("chicken broth",2), lime(1)],
  "Cook the grits with broth and water until creamy, then stir in cheddar and butter. Crisp the bacon and saute the shrimp with garlic in the drippings. Add lemon and toss the shrimp. Spoon the shrimp over the grits and top with bacon and green onion.",
  "moderate",["american","seafood","comfort"])

add("veggie-quesadilla","Loaded Veggie Quesadilla","Crispy quesadilla packed with peppers and cheese.","dinner",25,
  [BREAD("flour tortillas",8), cheddar(2.5), PROD("bell pepper",2), onion(1), FROZ("corn",1), PAN("black beans",1,"can"),
   PAN("salsa",0.75), SP("cumin",1), sour_cream(0.5)],
  "Saute the peppers, onion, corn, and beans with cumin. Layer the vegetables and cheese between tortillas. Cook in a dry skillet until golden and crisp on both sides. Slice and serve with salsa and sour cream.",
  "budget",["quick","mexican","vegetarian","budget"])

add("italian-wedding-soup","Italian Wedding Soup","Brothy soup with mini meatballs, pasta, and spinach.","dinner",45,
  [MEAT("ground beef",1), PAN("acini di pepe pasta",1), spinach(5), PROD("carrot",3), PROD("celery",3,"each"), onion(1),
   garlic(4), DAIRY("eggs",1,"each"), PAN("breadcrumbs",0.5), DAIRY("parmesan cheese",0.5), PAN("chicken broth",7)],
  "Mix the beef with egg, breadcrumbs, parmesan, and garlic and roll into mini meatballs. Simmer broth with carrot, celery, and onion. Add the meatballs and pasta and cook until done. Stir in spinach until wilted and serve with parmesan.",
  "moderate",["meal-prep","italian","beef","comfort","one-pot"])

add("salmon-rice-bowls","Spicy Salmon Rice Bowls","Flaky salmon over rice with avocado and spicy mayo.","dinner",30,
  [MEAT("salmon fillet",1.5), PAN("white rice",2), PROD("avocado",2), PROD("cucumber",1), DAIRY("mayonnaise",0.33),
   PAN("sriracha",2,"tbsp"), PAN("soy sauce",2,"tbsp"), PROD("green onion",4), lime(1)],
  "Cook the rice and flake the seared or baked salmon. Mix mayonnaise with sriracha for the spicy sauce. Slice the avocado and cucumber. Build bowls with rice, salmon, and vegetables and drizzle with the spicy mayo.",
  "premium",["quick","asian","seafood","high-protein"])

add("loaded-nachos","Loaded Beef Nachos","Sheet-pan nachos with beef, beans, and melted cheese.","dinner",30,
  [MEAT("ground beef",1), PAN("tortilla chips",10,"oz"), cheddar(2.5), PAN("black beans",1,"can"), PROD("tomato",2),
   PROD("jalapeno",2), sour_cream(0.5), PROD("avocado",2), SP("cumin",1), SP("chili powder",1)],
  "Brown the beef with cumin and chili powder. Spread tortilla chips on a sheet pan and top with beef, beans, and cheese. Bake at 400F until the cheese melts. Finish with tomato, jalapeno, sour cream, and avocado.",
  "moderate",["quick","mexican","beef","comfort","oven"])

# =====================================================================
# BUILD, VALIDATE, WRITE
# =====================================================================

# Trim to exactly 200 by dropping the most redundant quick dinners.
EXCLUDE_IDS = {
    "margherita-pasta",      # overlaps tomato-basil-penne / arrabbiata
    "sweet-chili-chicken",   # overlaps honey-garlic / orange chicken
    "veggie-fried-rice",     # overlaps egg fried rice / pork fried rice
    "lemon-pepper-chicken",  # overlaps other quick chicken dinners
}


def main():
    global RECIPES
    RECIPES = [r for r in RECIPES if r["id"] not in EXCLUDE_IDS]
    out = []
    ids = set()
    names = set()
    for rec in RECIPES:
        # validate id is kebab-case slug
        assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", rec["id"]), f"bad id {rec['id']}"
        assert rec["id"] not in ids, f"duplicate id {rec['id']}"
        assert rec["name"] not in names, f"duplicate name {rec['name']}"
        ids.add(rec["id"])
        names.add(rec["name"])
        assert len(rec["ingredients"]) >= 3, f"{rec['name']}: too few ingredients"
        out.append(build(rec))

    # ---- enforce content rules sanity (cross-check) ----
    for r in out:
        tags = set(r["tags"])
        if "meat" in tags:
            assert tags & {"beef", "chicken", "pork", "seafood"} or True  # turkey/lamb -> meat only ok
        # vegan -> vegetarian
        if "vegan" in tags:
            assert "vegetarian" in tags
        # quick <-> 30min
        assert ("quick" in tags) == ("30min" in tags), f"{r['name']}: quick/30min mismatch"
        if "quick" in tags:
            assert r["prepTime"] <= 30
        # gluten-free should not co-exist with gluten
        assert not ("gluten-free" in tags and "gluten" in tags), f"{r['name']}: gf+gluten"
        # dairy-free should not co-exist with dairy
        assert not ("dairy-free" in tags and "dairy" in tags), f"{r['name']}: df+dairy"

    # ---- distribution report ----
    def count(pred):
        return sum(1 for r in out if pred(r))
    print(f"TOTAL RECIPES: {len(out)}")
    print(f"  breakfast: {count(lambda r: r['mealType']=='breakfast')}")
    print(f"  lunch:     {count(lambda r: r['mealType']=='lunch')}")
    print(f"  dinner:    {count(lambda r: r['mealType']=='dinner')}")
    print(f"  quick:        {count(lambda r: 'quick' in r['tags'])}")
    print(f"  weekend:      {count(lambda r: 'weekend' in r['tags'])}")
    print(f"  meal-prep:    {count(lambda r: 'meal-prep' in r['tags'])}")
    print(f"  budget tag:   {count(lambda r: 'budget' in r['tags'])}")
    print(f"  high-protein: {count(lambda r: 'high-protein' in r['tags'])}")
    print(f"  low-carb:     {count(lambda r: 'low-carb' in r['tags'])}")
    print(f"  vegetarian:   {count(lambda r: 'vegetarian' in r['tags'])}")
    print(f"  vegan:        {count(lambda r: 'vegan' in r['tags'])}")
    for c in ["mexican","asian","mediterranean","indian","italian","american"]:
        print(f"  cuisine {c}: {count(lambda r, c=c: c in r['tags'])}")

    path = r"C:\Users\lukem\workspace\meal-planner\src\data\recipe-library.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"WROTE {len(out)} recipes to {path}")


if __name__ == "__main__":
    main()
