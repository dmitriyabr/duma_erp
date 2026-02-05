# Uniform Kits: Configurable Components with Variants

## 1. Обзор

Система позволяет создавать **uniform kits** (например, комплекты школьной формы), где:
- Цена кита фиксирована
- Состав компонентов можно настраивать **на момент продажи** (например, после примерки меняем размер рубашки с S на M)
- Компоненты могут быть либо **прямыми inventory items**, либо **variants** (группы взаимозаменяемых items)

### 1.1. Ключевые концепции

**Variant (Вариант):**
- Группа взаимозаменяемых items (например, "Рубашка модель X" с размерами S, M, L)
- Один и тот же item **может входить в несколько вариантов**
- Связь many-to-many через таблицу `item_variant_memberships`

**Kit Component Source Types:**
- `item` - прямой inventory item (как сейчас)
- `variant` - вариант, из которого можно выбрать конкретный item при продаже
  - При создании кита указывается `default_item_id` (какой item из варианта использовать по умолчанию)

**Editable Components:**
- Kit с флагом `is_editable_components = true`.
- При продаже **нельзя менять состав и количества** компонентов:
  - список компонентов и `quantity` берутся строго из `Kit.kit_items`;
  - пользователь может **только заменить конкретный `Item` внутри каждой позиции** (модель/размер).
- Поведение по типам компонента:
  - Если компонент - `item`: можно заменить на любой product `Item`;
  - Если компонент - `variant`: можно выбрать любой `Item` из этого варианта.

---

## 2. Модель данных

### 2.1. ItemVariantGroup (переименовать в ItemVariant)

```python
class ItemVariant(Base):
    """Группа взаимозаменяемых items (например, одна модель, разные размеры)."""
    
    __tablename__ = "item_variants"
    
    id: Mapped[int]
    name: Mapped[str]  # "Boys Shirt Model X"
    is_active: Mapped[bool]
    created_at: Mapped[DateTime]
    updated_at: Mapped[DateTime]
    
    # Relationships
    items: Mapped[list["Item"]] = relationship(
        "Item", 
        secondary="item_variant_memberships",
        back_populates="variants"
    )
```

### 2.2. ItemVariantMembership (новая таблица)

```python
class ItemVariantMembership(Base):
    """Связь many-to-many между Item и ItemVariant."""
    
    __tablename__ = "item_variant_memberships"
    
    id: Mapped[int]
    variant_id: Mapped[int] = mapped_column(ForeignKey("item_variants.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # Опционально: какой item по умолчанию в этом варианте
    
    created_at: Mapped[DateTime]
    
    # Unique constraint: один item может быть в варианте только один раз
    __table_args__ = (
        UniqueConstraint('variant_id', 'item_id', name='uq_variant_item'),
    )
```

### 2.3. Item (изменения)

```python
class Item(Base):
    # ... существующие поля ...
    
    # УБРАТЬ: variant_group_id (заменяется на many-to-many)
    
    # Relationships
    variants: Mapped[list["ItemVariant"]] = relationship(
        "ItemVariant",
        secondary="item_variant_memberships",
        back_populates="items"
    )
```

### 2.4. KitItem (изменения)

```python
class KitItem(Base):
    """Компонент кита - может быть прямым item или variant."""
    
    __tablename__ = "kit_items"
    
    id: Mapped[int]
    kit_id: Mapped[int] = mapped_column(ForeignKey("kits.id"))
    
    # Source type: 'item' или 'variant'
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'item' | 'variant'
    
    # Если source_type = 'item'
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    
    # Если source_type = 'variant'
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("item_variants.id"), nullable=True)
    default_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)  # Какой item из варианта использовать по умолчанию
    
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Relationships
    kit: Mapped["Kit"] = relationship("Kit", back_populates="kit_items")
    item: Mapped["Item | None"] = relationship("Item", foreign_keys=[item_id])
    variant: Mapped["ItemVariant | None"] = relationship("ItemVariant", foreign_keys=[variant_id])
    default_item: Mapped["Item | None"] = relationship("Item", foreign_keys=[default_item_id])
    
    # Validation: либо item_id, либо (variant_id + default_item_id) должны быть заполнены
    __table_args__ = (
        CheckConstraint(
            "(source_type = 'item' AND item_id IS NOT NULL AND variant_id IS NULL AND default_item_id IS NULL) OR "
            "(source_type = 'variant' AND variant_id IS NOT NULL AND default_item_id IS NOT NULL AND item_id IS NULL)",
            name='ck_kit_item_source'
        ),
    )
```

### 2.5. InvoiceLineComponent (без изменений)

Остаётся как есть:
- `invoice_line_id`
- `item_id` (фактический выбранный item)
- `quantity`

---

## 3. Бизнес-логика

### 3.1. Создание/редактирование Kit

**Backend (`ItemService.create_kit` / `update_kit`):**

1. Валидация `KitItemCreate`:
   - Если `source_type = 'item'`: проверяем, что `item_id` существует и это product
   - Если `source_type = 'variant'`: 
     - проверяем, что `variant_id` существует
     - проверяем, что `default_item_id` существует
     - проверяем, что `default_item_id` входит в `variant` (через `ItemVariantMembership`)

2. Создание `KitItem`:
   - Если `source_type = 'item'`: создаём с `item_id`, `variant_id = NULL`, `default_item_id = NULL`
   - Если `source_type = 'variant'`: создаём с `variant_id`, `default_item_id`, `item_id = NULL`

**Frontend (`CatalogPage`):**

В диалоге создания/редактирования кита, в секции Components:
- Для каждого компонента:
  - **Select "Source type":** `Inventory item` или `Variant`
  - Если `Inventory item`:
    - Select "Inventory item" (выпадашка всех product items)
  - Если `Variant`:
    - Select "Variant" (выпадашка всех активных variants)
    - Select "Default item" (выпадашка items, входящих в выбранный variant)

### 3.2. Продажа Editable Kit (смена только модели)

**Frontend (`CreateInvoicePage`):**

1. При выборе editable kit:
   - Инициализируем `components` из `Kit.kit_items` **один-в-один**:
     - Если `kit_item.source_type = 'item'`: `{ item_id: kit_item.item_id, quantity: kit_item.quantity }`;
     - Если `kit_item.source_type = 'variant'`: `{ item_id: kit_item.default_item_id, quantity: kit_item.quantity }`.
   - **Количество (`quantity`) и набор позиций не редактируются в UI**.

2. При замене компонента:
   - Если исходный компонент был из `variant`:
     - Показываем только items, входящие в этот variant (через `ItemVariantMembership`);
     - пользователь выбирает другой `Item` (например, рубашка M или L вместо S).
   - Если исходный компонент был прямым `item`:
     - Показываем все product items (на практике для униформы — обычно та же категория/модель).
   - В UI:
     - есть только селект выбора `Inventory item`;
     - поле `Qty` отображается, но заблокировано (`disabled`);
     - нет кнопок удаления или добавления компонентов.

**Backend (`InvoiceService._set_line_components`):**

1. Загружаем `Kit` с `kit_items` (включая `variant` и `default_item`).
2. Для каждого компонента в `components` (список того же размера, что `kit.kit_items`):
   - Находим соответствующий `KitItem` **по индексу** (позиция в массиве).
   - Если `KitItem.source_type = 'variant'`:
     - Проверяем, что выбранный `item_id` входит в `variant` (через `ItemVariantMembership`)
   - Если `KitItem.source_type = 'item'`:
     - Проверяем, что `item_id` существует и это product (как сейчас)

### 3.3. Резервация (ReservationService)

Поведение с учётом configurable components:

1. Если для строки есть `InvoiceLine.components`:
   - резервируем **ровно эти** `item_id` и `quantity` (один-в-один с компонентами строки);
2. Если компонентов нет:
   - fallback к `Kit.kit_items`:
     - если `source_type = 'item'` → используем `item_id`;
     - если `source_type = 'variant'` → используем `default_item_id`.

---

## 4. API изменения

### 4.1. ItemVariant endpoints

```python
# Переименовать /items/variant-groups → /items/variants
POST   /items/variants              # Создать вариант
GET    /items/variants              # Список вариантов (с items)
GET    /items/variants/{id}         # Один вариант
PATCH  /items/variants/{id}         # Обновить вариант (name, is_active, item_ids)
```

**ItemVariantUpdate:**
```python
class ItemVariantUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    item_ids: list[int] | None = None  # Полный список item_ids для варианта (пересоздаёт memberships)
```

### 4.2. KitItem schemas

```python
class KitItemCreate(BaseModel):
    source_type: Literal['item', 'variant']
    item_id: int | None = None  # Если source_type = 'item'
    variant_id: int | None = None  # Если source_type = 'variant'
    default_item_id: int | None = None  # Если source_type = 'variant'
    quantity: int = Field(1, ge=1)
    
    @model_validator(mode='after')
    def validate_source(self):
        if self.source_type == 'item':
            if not self.item_id:
                raise ValueError("item_id required when source_type='item'")
            if self.variant_id or self.default_item_id:
                raise ValueError("variant_id and default_item_id must be null when source_type='item'")
        elif self.source_type == 'variant':
            if not self.variant_id or not self.default_item_id:
                raise ValueError("variant_id and default_item_id required when source_type='variant'")
            if self.item_id:
                raise ValueError("item_id must be null when source_type='variant'")
        return self

class KitItemResponse(BaseModel):
    id: int
    source_type: str
    item_id: int | None
    variant_id: int | None
    default_item_id: int | None
    item_name: str | None = None  # Если source_type='item', иначе None
    variant_name: str | None = None  # Если source_type='variant', иначе None
    default_item_name: str | None = None  # Если source_type='variant'
    quantity: int
```

### 4.3. Kit endpoints

Без изменений в URL, но `KitCreate` / `KitUpdate` теперь принимают `items: list[KitItemCreate]` с новыми полями.

---

## 5. Миграция данных

### 5.1. Alembic migration

1. **Переименовать таблицу:**
   ```sql
   ALTER TABLE item_variant_groups RENAME TO item_variants;
   ```

2. **Создать таблицу `item_variant_memberships`:**
   ```sql
   CREATE TABLE item_variant_memberships (
       id BIGSERIAL PRIMARY KEY,
       variant_id BIGINT NOT NULL REFERENCES item_variants(id) ON DELETE CASCADE,
       item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
       is_default BOOLEAN DEFAULT FALSE,
       created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
       UNIQUE(variant_id, item_id)
   );
   ```

3. **Мигрировать данные из `items.variant_group_id`:**
   ```sql
   INSERT INTO item_variant_memberships (variant_id, item_id, is_default)
   SELECT variant_group_id, id, FALSE
   FROM items
   WHERE variant_group_id IS NOT NULL;
   ```

4. **Удалить колонку `items.variant_group_id`:**
   ```sql
   ALTER TABLE items DROP COLUMN variant_group_id;
   DROP INDEX IF EXISTS ix_items_variant_group_id;
   DROP FOREIGN KEY IF EXISTS fk_items_variant_group_id_item_variant_groups;
   ```

5. **Обновить `kit_items`:**
   ```sql
   -- Добавить новые колонки
   ALTER TABLE kit_items 
       ADD COLUMN source_type VARCHAR(20) DEFAULT 'item',
       ADD COLUMN variant_id BIGINT REFERENCES item_variants(id),
       ADD COLUMN default_item_id BIGINT REFERENCES items(id);
   
   -- Мигрировать существующие данные (все существующие = 'item')
   UPDATE kit_items SET source_type = 'item' WHERE source_type IS NULL;
   
   -- Добавить constraint
   ALTER TABLE kit_items 
       ADD CONSTRAINT ck_kit_item_source CHECK (
           (source_type = 'item' AND item_id IS NOT NULL AND variant_id IS NULL AND default_item_id IS NULL) OR
           (source_type = 'variant' AND variant_id IS NOT NULL AND default_item_id IS NOT NULL AND item_id IS NULL)
       );
   ```

---

## 6. Frontend изменения

### 6.1. CatalogPage (создание/редактирование кита)

В диалоге Kit, секция Components:
- Для каждого компонента:
  - **FormControl "Source type":**
    - `<Select value="item|variant">`
    - Options: "Inventory item", "Variant"
  - **Условный рендеринг:**
    - Если `source_type = 'item'`:
      - Select "Inventory item" (все product items)
    - Если `source_type = 'variant'`:
      - Select "Variant" (все активные variants)
      - Select "Default item" (items из выбранного variant, загружаются динамически)

### 6.2. CreateInvoicePage (продажа)

1. При выборе editable kit:
   - Загружаем `Kit` с `items` (включая `variant` и `default_item`)
   - Инициализируем `components`:
     - Если `kit_item.source_type = 'item'`: `{ item_id: kit_item.item_id, quantity: kit_item.quantity }`
     - Если `kit_item.source_type = 'variant'`: `{ item_id: kit_item.default_item_id, quantity: kit_item.quantity }`

2. При замене компонента:
   - Определяем исходный `KitItem` (по индексу)
   - Если `KitItem.source_type = 'variant'`:
     - Загружаем items из этого variant (через API `/items/variants/{id}` или фильтруем по `variant_id`)
     - Показываем только эти items в выпадашке
   - Если `KitItem.source_type = 'item'`:
     - Показываем все product items

---

## 7. Преимущества новой модели

1. **Гибкость:** Один item может быть в нескольких вариантах
2. **Явность:** В ките явно указано, какой компонент - прямой item, а какой - variant
3. **Удобство:** При создании кита можно выбрать default item из варианта
4. **Валидация:** Backend проверяет, что заменяющий item входит в variant

---

## 8. Обратная совместимость

- Существующие kits с `source_type = 'item'` продолжают работать
- Миграция автоматически конвертирует `variant_group_id` → `item_variant_memberships`
- Старые API endpoints `/items/variant-groups` можно оставить как deprecated или сразу переименовать
