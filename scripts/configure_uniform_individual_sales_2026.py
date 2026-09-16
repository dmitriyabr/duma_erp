"""Configure the 2026 uniform catalog for direct item sales.

Dry-run by default. Pass --apply to commit. Requires migration 053.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from decimal import Decimal

import asyncpg

MARKER = "uniform-individual-sales-2026"

PRICE_BY_ITEM: dict[str, Decimal] = {}


def add_numeric_range(prefix: str, small_price: str, large_price: str) -> None:
    for size in range(20, 28, 2):
        PRICE_BY_ITEM[f"{prefix} {size}"] = Decimal(small_price)
    for size in range(28, 36, 2):
        PRICE_BY_ITEM[f"{prefix} {size}"] = Decimal(large_price)


add_numeric_range("Shirt", "850.00", "950.00")
add_numeric_range("Trousers", "1250.00", "1450.00")
add_numeric_range("Dress", "1200.00", "1400.00")
add_numeric_range("Sweater", "1050.00", "1200.00")
add_numeric_range("Fleece", "2000.00", "2200.00")
add_numeric_range("Short", "700.00", "800.00")
add_numeric_range("Track Suite", "1700.00", "2000.00")
PRICE_BY_ITEM.update(
    {
        "Polo T-shirt S": Decimal("1100.00"),
        "Polo T-shirt M": Decimal("1100.00"),
        "Polo T-shirt L": Decimal("1200.00"),
        "Polo T-shirt XL": Decimal("1200.00"),
        "Tie short": Decimal("150.00"),
        "Tie long": Decimal("200.00"),
        "Socks girls S": Decimal("200.00"),
        "Socks girls M": Decimal("200.00"),
        "Socks girls L": Decimal("200.00"),
        "Socks boys S": Decimal("200.00"),
        "Socks boys M": Decimal("200.00"),
        "Socks boys L": Decimal("200.00"),
    }
)

MISSING_ITEMS = {
    "Shirt 34": "Shirt",
    "Short 34": "Shorts",
    "Track Suite 20": "Track suite",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor-id", type=int, default=2)
    return parser.parse_args()


async def next_uniform_sku(conn: asyncpg.Connection) -> str:
    while True:
        sequence = await conn.fetchrow(
            """SELECT id,last_number FROM document_sequences
               WHERE prefix='UNIFOR' AND year=0 FOR UPDATE"""
        )
        if sequence is None:
            number = 1
            await conn.execute(
                """INSERT INTO document_sequences(prefix,year,last_number)
                   VALUES('UNIFOR',0,$1)""",
                number,
            )
        else:
            number = int(sequence["last_number"]) + 1
            await conn.execute(
                "UPDATE document_sequences SET last_number=$2 WHERE id=$1",
                sequence["id"],
                number,
            )
        sku_code = f"UNIFOR-{number:06d}"
        exists = await conn.fetchval(
            """SELECT EXISTS(SELECT 1 FROM items WHERE sku_code=$1)
               OR EXISTS(SELECT 1 FROM kits WHERE sku_code=$1)""",
            sku_code,
        )
        if not exists:
            return sku_code


async def audit_item(
    conn: asyncpg.Connection,
    *,
    actor_id: int,
    item_id: int,
    sku_code: str,
    action: str,
    old_values: dict | None,
    new_values: dict,
) -> None:
    await conn.execute(
        """INSERT INTO audit_logs(user_id,action,entity_type,entity_id,
                                   entity_identifier,old_values,new_values,comment)
           VALUES($1,$2,'Item',$3,$4,$5::jsonb,$6::jsonb,$7)""",
        actor_id,
        action,
        item_id,
        sku_code,
        json.dumps(old_values, default=str) if old_values is not None else None,
        json.dumps(new_values, default=str),
        MARKER,
    )


async def configure(conn: asyncpg.Connection, actor_id: int) -> dict:
    if await conn.fetchval("SELECT COUNT(*) FROM audit_logs WHERE comment=$1", MARKER):
        return {"already_applied": True}
    if not await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE id=$1)", actor_id):
        raise RuntimeError(f"Actor user {actor_id} does not exist")
    columns = {
        row["column_name"]
        for row in await conn.fetch(
            """SELECT column_name FROM information_schema.columns
               WHERE table_name IN ('items','invoice_lines')
                 AND column_name IN ('is_sellable','item_id')"""
        )
    }
    if columns != {"is_sellable", "item_id"}:
        raise RuntimeError("Migration 053 must be applied first")

    category_id = await conn.fetchval("SELECT id FROM categories WHERE lower(name)='uniform'")
    if category_id is None:
        raise RuntimeError("Uniform category not found")

    target_prices = dict(PRICE_BY_ITEM)
    sock_names = await conn.fetch(
        """SELECT name FROM items
           WHERE category_id=$1 AND is_active=true AND item_type='product'
             AND price_type='standard' AND lower(name) LIKE 'socks%'""",
        category_id,
    )
    for row in sock_names:
        target_prices[row["name"]] = Decimal("200.00")

    created: list[str] = []
    for item_name, variant_name in MISSING_ITEMS.items():
        existing_item = await conn.fetchrow(
            "SELECT id,sku_code FROM items WHERE category_id=$1 AND name=$2",
            category_id,
            item_name,
        )
        variant_id = await conn.fetchval(
            "SELECT id FROM item_variants WHERE name=$1 AND is_active=true",
            variant_name,
        )
        if variant_id is None:
            raise RuntimeError(f"Active variant not found: {variant_name}")
        if existing_item is None:
            sku_code = await next_uniform_sku(conn)
            item_id = await conn.fetchval(
                """INSERT INTO items(category_id,sku_code,name,item_type,price_type,price,
                                      requires_full_payment,is_sellable,is_active)
                   VALUES($1,$2,$3,'product','standard',$4,true,true,true)
                   RETURNING id""",
                category_id,
                sku_code,
                item_name,
                target_prices[item_name],
            )
            created.append(item_name)
        else:
            item_id = existing_item["id"]
            sku_code = existing_item["sku_code"]
        await conn.execute(
            """INSERT INTO item_variant_memberships(variant_id,item_id,is_default)
               VALUES($1,$2,false) ON CONFLICT(variant_id,item_id) DO NOTHING""",
            variant_id,
            item_id,
        )
        await conn.execute(
            """INSERT INTO stock(item_id,quantity_on_hand,average_cost) VALUES($1,0,0)
               ON CONFLICT(item_id) DO NOTHING""",
            item_id,
        )
        if existing_item is None:
            await conn.execute(
                """INSERT INTO item_price_history(item_id,price,changed_by_id)
                   VALUES($1,$2,$3)""",
                item_id,
                target_prices[item_name],
                actor_id,
            )
            await audit_item(
                conn,
                actor_id=actor_id,
                item_id=item_id,
                sku_code=sku_code,
                action="item.create_uniform_catalog_size",
                old_values=None,
                new_values={
                    "name": item_name,
                    "variant": variant_name,
                    "price": target_prices[item_name],
                    "is_sellable": True,
                },
            )

    await conn.execute(
        "UPDATE items SET is_sellable=false WHERE category_id=$1",
        category_id,
    )

    updated: list[str] = []
    for item_name, price in target_prices.items():
        item = await conn.fetchrow(
            """SELECT id,sku_code,price,is_sellable,is_active,item_type,price_type
               FROM items WHERE category_id=$1 AND name=$2 FOR UPDATE""",
            category_id,
            item_name,
        )
        if item is None:
            raise RuntimeError(f"Catalog item not found after setup: {item_name}")
        if not item["is_active"] or item["item_type"] != "product":
            raise RuntimeError(f"Catalog item is not an active product: {item_name}")
        if item["price_type"] != "standard":
            raise RuntimeError(f"Catalog item does not use standard pricing: {item_name}")
        old_values = {
            "price": item["price"],
            "is_sellable": item["is_sellable"],
        }
        price_changed = item["price"] is None or Decimal(item["price"]) != price
        await conn.execute(
            "UPDATE items SET price=$2,is_sellable=true,updated_at=now() WHERE id=$1",
            item["id"],
            price,
        )
        if price_changed:
            await conn.execute(
                """INSERT INTO item_price_history(item_id,price,changed_by_id)
                   VALUES($1,$2,$3)""",
                item["id"],
                price,
                actor_id,
            )
        await audit_item(
            conn,
            actor_id=actor_id,
            item_id=item["id"],
            sku_code=item["sku_code"],
            action="item.enable_individual_sale",
            old_values=old_values,
            new_values={"price": price, "is_sellable": True},
        )
        updated.append(item_name)

    sellable_count = await conn.fetchval(
        "SELECT COUNT(*) FROM items WHERE category_id=$1 AND is_sellable=true",
        category_id,
    )
    return {
        "created": created,
        "updated_count": len(updated),
        "sellable_count": int(sellable_count),
    }


async def main() -> None:
    args = parse_args()
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+asyncpg://",
        "postgresql://",
        1,
    )
    conn = await asyncpg.connect(database_url)
    transaction = conn.transaction()
    await transaction.start()
    try:
        result = await configure(conn, args.actor_id)
        result["mode"] = "apply" if args.apply else "dry-run"
        if args.apply:
            await transaction.commit()
        else:
            await transaction.rollback()
        print(json.dumps(result, indent=2))
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
