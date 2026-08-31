from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.repository import Repository
from ..deps import get_repo
from .helpers import icon_url

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


class IngredientAdd(BaseModel):
    item_id: int
    qty: int


class RecipeCreate(BaseModel):
    name: str
    output_item_id: int
    output_qty: int
    ingredients: list[IngredientAdd]


@router.get("")
async def get_recipes(repo: Repository = Depends(get_repo)) -> dict:
    recipes = await repo.get_recipes()
    for r in recipes:
        r["output_icon"] = icon_url(r.get("output_icon"), r["output_item_id"])
        r["wiki_url"] = f"https://runescape.wiki/w/{r['output_name'].replace(' ', '_')}"
        for ing in r.get("ingredients", []):
            ing["icon_url"] = icon_url(ing.get("icon"), ing["item_id"])
            ing["wiki_url"] = f"https://runescape.wiki/w/{ing['name'].replace(' ', '_')}"
    return {"recipes": recipes}


@router.post("", status_code=201)
async def create_recipe(data: RecipeCreate, repo: Repository = Depends(get_repo)) -> dict:
    if not await repo.get_item(data.output_item_id):
        raise HTTPException(404, f"Unknown output item id {data.output_item_id}")
        
    for ing in data.ingredients:
        if not await repo.get_item(ing.item_id):
            raise HTTPException(404, f"Unknown ingredient item id {ing.item_id}")

    recipe_id = await repo.create_recipe(
        name=data.name.strip(),
        output_item_id=data.output_item_id,
        output_qty=data.output_qty,
        ingredients=[{"item_id": ing.item_id, "qty": ing.qty} for ing in data.ingredients],
    )
    return {"status": "ok", "id": recipe_id}


@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: int, repo: Repository = Depends(get_repo)) -> dict:
    deleted = await repo.delete_recipe(recipe_id)
    if not deleted:
        raise HTTPException(404, "Recipe not found")
    return {"status": "ok", "id": recipe_id}
