// Fallback modal handlers to keep settings button working.
document.addEventListener('click', (e) => {
  const target = e.target;
  if (!target || typeof target.closest !== 'function') return;

  const openBtn = target.closest('[data-event-settings]');
  if (openBtn) {
    const eventId = openBtn.getAttribute('data-event-settings');
    const modal = document.getElementById(`event-modal-${eventId}`);
    if (modal) {
      modal.classList.add('active');
      document.body.classList.add('modal-open');
    }
    return;
  }

  const closeBtn = target.closest('[data-close-modal]');
  if (closeBtn) {
    const modalId = closeBtn.getAttribute('data-close-modal');
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
      document.body.classList.remove('modal-open');
    }
    return;
  }

  if (target.classList && target.classList.contains('modal')) {
    target.classList.remove('active');
    document.body.classList.remove('modal-open');
  }
});

(function () {
  const showAllCollapsibles = () => {
    document.querySelectorAll(".collapsible__content").forEach((content) => {
      content.hidden = false;
    });
  };

  const safeRun = (label, fn) => {
    try {
      fn();
    } catch (err) {
      console.error(`Admin UI Init Error (${label})`, err);
      showAllCollapsibles();
    }
  };

  safeRun("modals", () => {
    // Modal functionality
    const openModal = (modalId) => {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.add('active');
        document.body.classList.add('modal-open');
      }
    };

    const closeModal = (modalId) => {
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.classList.remove('active');
        document.body.classList.remove('modal-open');
      }
    };

    // Open new event modal
    const newEventBtn = document.getElementById('new-event-btn');
    if (newEventBtn) {
      newEventBtn.addEventListener('click', () => openModal('new-event-modal'));
    }

    // Open event settings modals
    document.querySelectorAll('[data-event-settings]').forEach(btn => {
      btn.addEventListener('click', () => {
        const eventId = btn.getAttribute('data-event-settings');
        openModal(`event-modal-${eventId}`);
      });
    });

    // Close modals
    document.querySelectorAll('[data-close-modal]').forEach(btn => {
      btn.addEventListener('click', () => {
        const modalId = btn.getAttribute('data-close-modal');
        closeModal(modalId);
      });
    });

    // Close modal when clicking outside
    document.querySelectorAll('.modal').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
          closeModal(modal.id);
        }
      });
    });

    // Close modal on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
          closeModal(modal.id);
        });
      }
    });
  });

  const fallbackColor = "#1f2a44";
  const defaultCategory = "Standard";

    const getTextContent = (id) => {
      const el = document.getElementById(id);
      return el ? el.textContent : "";
    };

    const parseJson = (value, fallback) => {
      if (!value) return fallback;
      try { return JSON.parse(value); } catch (err) { return fallback; }
    };

    const eventData = parseJson(getTextContent("event-settings-data"), {});
    const defaultButtons = parseJson(getTextContent("default-buttons-data"), []);
    const shotDefaults = parseJson(
      getTextContent("shotcounter-defaults-data"),
      {
        background_color: "#0b1222",
        primary_color: "#1e293b",
        secondary_color: "#38bdf8",
        tertiary_color: "#34d399",
        title_size: 3.2,
        team_size: 1.6,
        leaderboard_limit: 10,
        leaderboard_layout: "stacked",
      }
    );

    const priceDefaults = parseJson(
      getTextContent("price-list-defaults-data"),
      {
        font_size: 1.4,
        rotation_seconds: 10,
        background_mode: "none",
        background_color: "#0b1222",
        background_image: null,
        enabled_categories: [],
      }
    );

    safeRun("collapsibles", () => {
      document.querySelectorAll("[data-collapsible]").forEach((wrap) => {
        const content = wrap.querySelector(".collapsible__content");
        const toggle = wrap.querySelector("[data-toggle]");
        if (!content || !toggle) return;
        const startOpen = wrap.dataset.startOpen === "true";
        if (startOpen) content.hidden = false;
        const syncLabel = () => { toggle.textContent = content.hidden ? "Details einblenden" : "Details ausblenden"; };
        syncLabel();
        toggle.addEventListener("click", () => { content.hidden = !content.hidden; syncLabel(); });
      });
    });

    const sanitizeColor = (value) => {
      if (typeof value !== "string") return fallbackColor;
      const hex = value.trim();
      return /^#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$/.test(hex) ? hex : fallbackColor;
    };

    const clampNumber = (value, fallback, min, max) => {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return fallback;
      return Math.min(max, Math.max(min, parsed));
    };

    const normalizeDepotPrice = (value) => {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) return 2;
      return Math.max(0, Math.round(parsed));
    };

    const normalizeItem = (item, index) => {
      const safeItem = item || {};
      const rawLabel = safeItem.label ?? safeItem.name ?? "";
      const label = String(rawLabel).trim() || "Produkt " + (index + 1);
      const rawName = safeItem.name ?? label ?? "produkt-" + (index + 1);
      const name = String(rawName).trim();
      const price = Number.isFinite(Number(safeItem.price)) ? Number(safeItem.price) : 0;
      const hasDepot = safeItem.has_depot === true;
      return {
        name,
        label,
        price,
        css_class: safeItem.css_class || "custom",
        color: sanitizeColor(safeItem.color || ""),
        category: String(safeItem.category ?? defaultCategory),
        show_in_cashier: safeItem.show_in_cashier !== false,
        show_in_price_list: safeItem.show_in_price_list !== false,
        has_depot: hasDepot,
      };
    };

    // Shotcounter-Settings
    safeRun("shot-settings", () => {
      document.querySelectorAll("[data-shot-settings]").forEach((wrapper) => {
        const hidden = wrapper.querySelector('input[name="shotcounter_settings"]');
        const defaults = { ...shotDefaults, ...parseJson(wrapper.dataset.defaults, shotDefaults) };
        const current = parseJson(wrapper.dataset.current, {});
        let settings = { ...defaults, ...current };

        const syncInputs = () => {
          wrapper.querySelectorAll("[data-shot-field]").forEach((input) => {
            const key = input.dataset.shotField;
            if (!key) return;
            if (input.type === "color") {
              input.value = sanitizeColor(settings[key] || defaults[key] || fallbackColor);
            } else if (input.type === "number") {
              input.value = settings[key] ?? defaults[key] ?? "";
            } else if (input.tagName === "SELECT") {
              input.value = settings[key] ?? defaults[key] ?? "";
            }
          });
        };

        const syncHidden = () => {
          if (hidden) hidden.value = JSON.stringify(settings);
        };

        wrapper.querySelectorAll("[data-shot-field]").forEach((input) => {
          const key = input.dataset.shotField;
          if (!key) return;
          input.addEventListener("input", () => {
            if (input.type === "color") {
              settings[key] = sanitizeColor(input.value || defaults[key] || fallbackColor);
            } else if (input.type === "number") {
              const min = key === "leaderboard_limit" ? 1 : 0.5;
              const max = key === "leaderboard_limit" ? 50 : 10;
              settings[key] = clampNumber(input.value, defaults[key], min, max);
            } else if (input.tagName === "SELECT") {
              settings[key] = input.value;
            }
            syncHidden();
          });
        });

        wrapper.shotSettingsApi = {
          getSettings: () => ({ ...settings }),
          setSettings: (data) => {
            settings = { ...defaults, ...(data || {}) };
            syncInputs();
            syncHidden();
          },
        };

        syncInputs();
        syncHidden();
      });
    });

    // Produkt-Editor
    safeRun("product-editor", () => {
      document.querySelectorAll("[data-product-editor]").forEach((wrapper) => {
        const form = wrapper.closest("form");
        const statusEl = form ? form.querySelector('[data-form-status]') : null;
        const addButton = wrapper.querySelector("[data-add-product]");
        const cashierPreview = wrapper.querySelector("[data-product-preview='cashier']");
        const pricePreview = wrapper.querySelector("[data-product-preview='price']");
        const list = wrapper.querySelector("[data-product-list]");
        const categoryOrderList = wrapper.querySelector("[data-category-order-list]");
        const addCategoryBtn = wrapper.querySelector("[data-add-category]");
        const hidden = wrapper.querySelector('input[name="kassensystem_settings"]');
        const importInput = wrapper.querySelector("[data-product-import]");
        const exportButton = wrapper.querySelector("[data-product-export]");
        const depotInput = form ? form.querySelector("[data-depot-price]") : null;

      let baseSettings = {};
      try { baseSettings = JSON.parse(hidden.value || "{}"); } catch (err) { baseSettings = {}; }

      let parsedItems = [];
      try {
        // First try to read from saved data (hidden input), then fallback to template data
        if (baseSettings.items && Array.isArray(baseSettings.items)) {
          parsedItems = baseSettings.items;
        } else {
          parsedItems = JSON.parse(wrapper.dataset.items || "[]");
        }
      } catch (err) { parsedItems = []; }

      let items = Array.isArray(parsedItems) ? parsedItems.map(normalizeItem) : [];
      let depotPrice = normalizeDepotPrice(baseSettings.depot_price);
      let categoryOrder = Array.isArray(baseSettings.category_order)
        ? baseSettings.category_order.map((name) => String(name || "").trim()).filter(Boolean)
        : [];
      let categoryVisibility =
        baseSettings.category_visibility && typeof baseSettings.category_visibility === "object"
          ? { ...baseSettings.category_visibility }
          : {};
      if (!items.length) {
        items = [normalizeItem({ name: "Produkt", label: "Neues Produkt", price: 0, color: fallbackColor }, 0)];
      }

      if (depotInput) {
        depotInput.value = depotPrice;
        depotInput.addEventListener("input", () => {
          depotPrice = normalizeDepotPrice(depotInput.value);
          depotInput.value = depotPrice;
          renderPreview();
          syncHidden();
        });
      }

      const normalizeCategoryOrder = (categories) => {
        const clean = [];
        (categoryOrder || []).forEach((name) => {
          const trimmed = String(name || "").trim();
          if (trimmed && categories.includes(trimmed) && !clean.includes(trimmed)) {
            clean.push(trimmed);
          }
        });
        categories.forEach((name) => {
          if (name && !clean.includes(name)) {
            clean.push(name);
          }
        });
        categoryOrder = clean;
        return clean;
      };

      const normalizeCategoryVisibility = (categories) => {
        const next = {};
        categories.forEach((name) => {
          const existing = categoryVisibility && typeof categoryVisibility === "object" ? categoryVisibility[name] || {} : {};
          next[name] = {
            cashier: existing.cashier !== false,
            price_list: existing.price_list !== false,
          };
        });
        categoryVisibility = next;
        return next;
      };

      const syncHidden = () => {
        const categories = getAllCategories();
        normalizeCategoryOrder(categories);
        normalizeCategoryVisibility(categories);
        hidden.value = JSON.stringify({
          ...baseSettings,
          depot_price: depotPrice,
          category_order: categoryOrder,
          category_visibility: categoryVisibility,
          items,
        });
        wrapper.dispatchEvent(new CustomEvent("product-editor:change", { detail: { categories } }));
      };

      const getSortedItems = (filterKey) => {
        return items
          .filter((item) => {
            if (!item) return false;
            const category = String(item.category || defaultCategory).trim() || defaultCategory;
            const visibility = categoryVisibility && typeof categoryVisibility === "object" ? categoryVisibility[category] : null;
            if (filterKey === "cashier") {
              if (visibility && visibility.cashier === false) return false;
              return item.show_in_cashier !== false;
            }
            if (filterKey === "price") {
              if (visibility && visibility.price_list === false) return false;
              return item.show_in_price_list !== false;
            }
            return true;
          })
          .slice()
          .sort((a, b) => {
            const catA = String(a.category || defaultCategory).trim();
            const catB = String(b.category || defaultCategory).trim();
            const order = normalizeCategoryOrder(getAllCategories());
            const idxA = order.indexOf(catA);
            const idxB = order.indexOf(catB);
            if (idxA !== idxB) {
              return (idxA === -1 ? 9999 : idxA) - (idxB === -1 ? 9999 : idxB);
            }
            const labelA = String(a.label || a.name || "").toLowerCase();
            const labelB = String(b.label || b.name || "").toLowerCase();
            if (labelA < labelB) return -1;
            if (labelA > labelB) return 1;
            return 0;
          });
      };

      const renderCashierPreview = () => {
        if (!cashierPreview) return;
        cashierPreview.innerHTML = "";
        const sorted = getSortedItems("cashier");
        if (!sorted.length) {
          cashierPreview.innerHTML = "<div class='muted'>Keine Produkte sichtbar.</div>";
          return;
        }
        const bucket = new Map();
        sorted.forEach((item) => {
          const category = String(item.category || defaultCategory).trim() || defaultCategory;
          if (!bucket.has(category)) bucket.set(category, []);
          bucket.get(category).push(item);
        });
        const orderedCategories = getOrderedCategories(Array.from(bucket.keys()));
        orderedCategories.forEach((category) => {
          const categoryItems = bucket.get(category) || [];
          const section = document.createElement("div");
          section.className = "price-preview-category";
          const title = document.createElement("h4");
          title.textContent = category;
          section.appendChild(title);
          const list = document.createElement("div");
          list.style.display = "grid";
          list.style.gridTemplateColumns = "repeat(auto-fill, minmax(150px, 1fr))";
          list.style.gap = "0.6rem";
          categoryItems.forEach((item) => {
            const displayPrice = Number(item.price || 0) + (item.has_depot ? Number(depotPrice || 0) : 0);
            const card = document.createElement("div");
            card.className = "product-preview-card";
            card.style.background = sanitizeColor(item.color);
            card.innerHTML = `<small>${displayPrice} CHF${item.has_depot ? " (inkl. Depot)" : ""}</small><div style=\"font-weight:700;\">${item.label}</div>`;
            list.appendChild(card);
          });
          section.appendChild(list);
          cashierPreview.appendChild(section);
        });
      };

      const renderPricePreview = () => {
        if (!pricePreview) return;
        pricePreview.innerHTML = "";
        const sorted = getSortedItems("price");
        if (!sorted.length) {
          pricePreview.innerHTML = "<div class='muted'>Keine Produkte sichtbar.</div>";
          return;
        }
        const bucket = new Map();
        sorted.forEach((item) => {
          const category = String(item.category || defaultCategory).trim() || defaultCategory;
          if (!bucket.has(category)) bucket.set(category, []);
          bucket.get(category).push(item);
        });
        const orderedCategories = getOrderedCategories(Array.from(bucket.keys()));
        orderedCategories.forEach((category) => {
          const categoryItems = bucket.get(category) || [];
          const section = document.createElement("div");
          section.className = "price-preview-category";
          const title = document.createElement("h4");
          title.textContent = category;
          section.appendChild(title);
          categoryItems.forEach((item) => {
            const row = document.createElement("div");
            row.className = "price-preview-item";
            row.innerHTML = `<span>${item.label || ""}</span><span>${Number(item.price || 0)} CHF</span>`;
            section.appendChild(row);
          });
          pricePreview.appendChild(section);
        });
      };

      const renderPreview = () => {
        renderCashierPreview();
        renderPricePreview();
      };

      const getAllCategories = () => {
        // Collect unique categories from all items in current editor
        const categories = new Set();
        items.forEach(item => {
          const rawCategory = item ? item.category : "";
          const category = String(rawCategory ?? "").trim();
          if (category) {
            categories.add(category);
          }
        });
        categoryOrder.forEach((name) => {
          const trimmed = String(name || "").trim();
          if (trimmed) categories.add(trimmed);
        });
        Object.keys(categoryVisibility || {}).forEach((name) => {
          const trimmed = String(name || "").trim();
          if (trimmed) categories.add(trimmed);
        });
        return Array.from(categories).sort();
      };

      const getOrderedCategories = (categories) => normalizeCategoryOrder(categories);

      const renderCategoryOrder = () => {
        if (!categoryOrderList) return;
        const categories = getAllCategories();
        const ordered = getOrderedCategories(categories);
        normalizeCategoryVisibility(categories);
        categoryOrderList.innerHTML = "";

        const renameCategory = (oldName, newNameRaw) => {
          const newName = String(newNameRaw || "").trim();
          if (!newName || newName === oldName) return;
          if (categories.includes(newName)) return;

          items.forEach((item) => {
            const category = String(item.category || defaultCategory).trim() || defaultCategory;
            if (category === oldName) {
              item.category = newName;
            }
          });

          categoryOrder = categoryOrder.map((name) => (name === oldName ? newName : name));
          if (categoryVisibility[oldName]) {
            categoryVisibility[newName] = categoryVisibility[oldName];
            delete categoryVisibility[oldName];
          }

          renderList();
          renderPreview();
          renderCategoryOrder();
          syncHidden();
        };

        ordered.forEach((name, index) => {
          const row = document.createElement("div");
          row.className = "category-order__item";
          const nameWrap = document.createElement("div");
          nameWrap.className = "category-order__name";
          const nameInput = document.createElement("input");
          nameInput.value = name;
          nameInput.addEventListener("change", () => {
            renameCategory(name, nameInput.value);
          });
          nameInput.addEventListener("blur", () => {
            renameCategory(name, nameInput.value);
          });
          nameWrap.appendChild(nameInput);

          const toggles = document.createElement("div");
          toggles.className = "visibility-toggle";

          const cashierLabel = document.createElement("label");
          cashierLabel.className = "pill-toggle";
          const cashierToggle = document.createElement("input");
          cashierToggle.type = "checkbox";
          cashierToggle.checked = !(categoryVisibility[name] && categoryVisibility[name].cashier === false);
          cashierToggle.addEventListener("change", () => {
            categoryVisibility[name] = {
              cashier: cashierToggle.checked,
              price_list: !(categoryVisibility[name] && categoryVisibility[name].price_list === false),
            };
            renderPreview();
            syncHidden();
          });
          const cashierText = document.createElement("span");
          cashierText.textContent = "Kasse";
          cashierLabel.append(cashierToggle, cashierText);

          const priceLabel = document.createElement("label");
          priceLabel.className = "pill-toggle";
          const priceToggle = document.createElement("input");
          priceToggle.type = "checkbox";
          priceToggle.checked = !(categoryVisibility[name] && categoryVisibility[name].price_list === false);
          priceToggle.addEventListener("change", () => {
            categoryVisibility[name] = {
              cashier: !(categoryVisibility[name] && categoryVisibility[name].cashier === false),
              price_list: priceToggle.checked,
            };
            renderPreview();
            syncHidden();
          });
          const priceText = document.createElement("span");
          priceText.textContent = "Preisliste";
          priceLabel.append(priceToggle, priceText);

          toggles.append(cashierLabel, priceLabel);

          const actions = document.createElement("div");
          actions.className = "category-order__actions";

          const upBtn = document.createElement("button");
          upBtn.type = "button";
          upBtn.className = "secondary";
          upBtn.textContent = "↑";
          upBtn.disabled = index === 0;
          upBtn.addEventListener("click", () => {
            if (index <= 0) return;
            const moved = categoryOrder.splice(index, 1)[0];
            categoryOrder.splice(index - 1, 0, moved);
            renderCategoryOrder();
            renderPreview();
            syncHidden();
          });

          const downBtn = document.createElement("button");
          downBtn.type = "button";
          downBtn.className = "secondary";
          downBtn.textContent = "↓";
          downBtn.disabled = index >= ordered.length - 1;
          downBtn.addEventListener("click", () => {
            if (index >= ordered.length - 1) return;
            const moved = categoryOrder.splice(index, 1)[0];
            categoryOrder.splice(index + 1, 0, moved);
            renderCategoryOrder();
            renderPreview();
            syncHidden();
          });

          actions.append(upBtn, downBtn);
          row.append(nameWrap, toggles, actions);
          categoryOrderList.appendChild(row);
        });
      };

      const addCategory = (nameRaw) => {
        const name = String(nameRaw || "").trim();
        if (!name) return;
        const categories = getAllCategories();
        if (categories.includes(name)) return;
        categoryOrder.push(name);
        categoryVisibility[name] = { cashier: true, price_list: true };
        renderCategoryOrder();
        renderPreview();
        syncHidden();
      };

      if (addCategoryBtn) {
        addCategoryBtn.addEventListener("click", () => {
          const name = prompt("Neue Kategorie:");
          if (!name) return;
          addCategory(name);
        });
      }

      const renderList = () => {
        list.innerHTML = "";

        // Create a single datalist for all category inputs in this editor
        const datalistId = `categories-datalist-${wrapper.dataset.scope || Date.now()}`;
        const datalist = document.createElement("datalist");
        datalist.id = datalistId;

        // Populate datalist with unique categories
        const categories = getAllCategories();
        categories.forEach(cat => {
          const option = document.createElement("option");
          option.value = cat;
          datalist.appendChild(option);
        });
        list.appendChild(datalist);

        const orderedCategories = getOrderedCategories(categories);
        const categoryIndex = new Map();
        orderedCategories.forEach((name, idx) => categoryIndex.set(name, idx));

        const sortedItems = items.slice().sort((a, b) => {
          const catA = String(a.category || defaultCategory).trim() || defaultCategory;
          const catB = String(b.category || defaultCategory).trim() || defaultCategory;
          const idxA = categoryIndex.has(catA) ? categoryIndex.get(catA) : 9999;
          const idxB = categoryIndex.has(catB) ? categoryIndex.get(catB) : 9999;
          if (idxA !== idxB) return idxA - idxB;
          const labelA = String(a.label || a.name || "").toLowerCase();
          const labelB = String(b.label || b.name || "").toLowerCase();
          if (labelA < labelB) return -1;
          if (labelA > labelB) return 1;
          return 0;
        });

        sortedItems.forEach((item, index) => {
          const row = document.createElement("div");
          row.className = "product-row";

          const nameContainer = document.createElement("div");
          nameContainer.className = "stack";
          const nameLabel = document.createElement("label");
          nameLabel.textContent = "Schlüssel (interner Name)";
          const nameInput = document.createElement("input");
          nameInput.value = item.name;
          nameInput.placeholder = "unique-key";
          nameInput.addEventListener("input", () => {
            item.name = nameInput.value.trim();
            syncHidden();
          });
          nameContainer.append(nameLabel, nameInput);

          const labelContainer = document.createElement("div");
          labelContainer.className = "stack";
          const labelLabel = document.createElement("label");
          labelLabel.textContent = "Titel (Anzeige)";
          const labelInput = document.createElement("input");
          labelInput.value = item.label;
          labelInput.placeholder = "z.B. Bier";
          labelInput.addEventListener("input", () => {
            item.label = labelInput.value;
            if (!item.name.trim()) {
              item.name = labelInput.value;
              nameInput.value = item.name;
            }
            renderPreview();
            syncHidden();
          });
          labelContainer.append(labelLabel, labelInput);

          const priceContainer = document.createElement("div");
          priceContainer.className = "stack";
          const priceLabel = document.createElement("label");
          priceLabel.textContent = "Preis (CHF)";
          const priceInput = document.createElement("input");
          priceInput.type = "number";
          priceInput.step = "1";
          priceInput.value = item.price;
          priceInput.addEventListener("input", () => {
            const parsed = Number(priceInput.value);
            item.price = Number.isFinite(parsed) ? parsed : 0;
            renderPreview();
            syncHidden();
          });
          priceContainer.append(priceLabel, priceInput);

          const depotContainer = document.createElement("div");
          depotContainer.className = "stack";
          const depotLabel = document.createElement("label");
          depotLabel.textContent = "Depot";
          const depotToggleWrap = document.createElement("div");
          depotToggleWrap.style.display = "flex";
          depotToggleWrap.style.alignItems = "center";
          depotToggleWrap.style.gap = "0.5rem";

          const depotToggle = document.createElement("input");
          depotToggle.type = "checkbox";
          depotToggle.checked = item.has_depot === true;
          depotToggle.addEventListener("change", () => {
            item.has_depot = depotToggle.checked;
            renderPreview();
            syncHidden();
          });

          const depotText = document.createElement("span");
          depotText.textContent = "Aktiv";
          depotToggleWrap.append(depotToggle, depotText);
          depotContainer.append(depotLabel, depotToggleWrap);

          const colorContainer = document.createElement("div");
          colorContainer.className = "stack";
          const colorLabel = document.createElement("label");
          colorLabel.textContent = "Hintergrundfarbe";
          const colorInput = document.createElement("input");
          colorInput.type = "color";
          colorInput.className = "color-input";
          colorInput.value = sanitizeColor(item.color);
          colorInput.addEventListener("input", () => {
            item.color = sanitizeColor(colorInput.value);
            renderPreview();
            syncHidden();
          });
          colorContainer.append(colorLabel, colorInput);

          const categoryContainer = document.createElement("div");
          categoryContainer.className = "stack";
          const categoryLabel = document.createElement("label");
          categoryLabel.textContent = "Kategorie";
          const categoryInput = document.createElement("input");
          categoryInput.setAttribute("list", datalistId);
          categoryInput.value = String(item.category ?? defaultCategory);
          categoryInput.placeholder = "Wählen oder neue Kategorie eingeben";
          categoryInput.addEventListener("input", () => {
            item.category = categoryInput.value.trim() || defaultCategory;
            renderPreview();
            renderCategoryOrder();
            syncHidden();
          });
          categoryInput.addEventListener("change", () => {
            // Commit category selection/new entry and update datalist
            const newCategory = categoryInput.value.trim() || defaultCategory;
            item.category = newCategory;
            renderPreview();
            renderCategoryOrder();
            syncHidden();

            if (newCategory && newCategory !== defaultCategory) {
              const categories = getAllCategories();
              if (!categories.includes(newCategory)) {
                // Re-render list to update datalist with new category
                renderList();
              }
            }
          });
          categoryContainer.append(categoryLabel, categoryInput);

          const visibilityContainer = document.createElement("div");
          visibilityContainer.className = "stack";
          const visibilityLabel = document.createElement("label");
          visibilityLabel.textContent = "Sichtbarkeit";
          const visibilityGroup = document.createElement("div");
          visibilityGroup.className = "visibility-toggle";
          const cashierLabel = document.createElement("label");
          cashierLabel.className = "pill-toggle";
          const cashierToggle = document.createElement("input");
          cashierToggle.type = "checkbox";
          cashierToggle.checked = item.show_in_cashier !== false;
          cashierToggle.addEventListener("change", () => {
            item.show_in_cashier = cashierToggle.checked;
            syncHidden();
          });
          const cashierText = document.createElement("span");
          cashierText.textContent = "Kasse";
          cashierLabel.append(cashierToggle, cashierText);

          const priceListLabel = document.createElement("label");
          priceListLabel.className = "pill-toggle";
          const priceToggle = document.createElement("input");
          priceToggle.type = "checkbox";
          priceToggle.checked = item.show_in_price_list !== false;
          priceToggle.addEventListener("change", () => {
            item.show_in_price_list = priceToggle.checked;
            syncHidden();
          });
          const priceText = document.createElement("span");
          priceText.textContent = "Preisliste";
          priceListLabel.append(priceToggle, priceText);

          visibilityGroup.append(cashierLabel, priceListLabel);
          visibilityContainer.append(visibilityLabel, visibilityGroup);

          const actions = document.createElement("div");
          actions.className = "row-actions";
          const removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.className = "danger";
          removeBtn.textContent = "Entfernen";
          removeBtn.addEventListener("click", () => {
            items.splice(index, 1);
            if (!items.length) {
              items.push(normalizeItem({ name: "produkt", label: "Produkt", price: 0, color: fallbackColor }, 0));
            }
            renderList();
            renderPreview();
            renderCategoryOrder();
            syncHidden();
          });
          actions.appendChild(removeBtn);

          row.append(labelContainer, nameContainer, priceContainer, depotContainer, colorContainer, categoryContainer, visibilityContainer, actions);
          list.appendChild(row);
        });
      };

      if (addButton) {
        addButton.addEventListener("click", () => {
          items.push(
            normalizeItem(
              {
                name: "produkt-" + Date.now(),
                label: "Neues Produkt",
                price: 0,
                color: fallbackColor,
              },
              items.length
            )
          );
          renderList();
          renderPreview();
          renderCategoryOrder();
          syncHidden();
        });
      }

      if (importInput) {
        importInput.addEventListener("change", (ev) => {
          const file = ev.target.files && ev.target.files[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = () => {
            const data = parseJson(reader.result, null);
            if (!data) {
              if (statusEl) {
                statusEl.style.display = 'inline';
                statusEl.style.color = '#ef4444';
                statusEl.textContent = 'Fehler: JSON konnte nicht gelesen werden.';
                setTimeout(() => { statusEl.style.display = 'none'; }, 4000);
              }
              return;
            }
            const importedItems = Array.isArray(data && data.items) ? data.items : Array.isArray(data) ? data : [];
            baseSettings = data && typeof data === "object" && !Array.isArray(data) ? { ...data } : {};
            categoryOrder = Array.isArray(baseSettings.category_order)
              ? baseSettings.category_order.map((name) => String(name || "").trim()).filter(Boolean)
              : [];
            categoryVisibility =
              baseSettings.category_visibility && typeof baseSettings.category_visibility === "object"
                ? { ...baseSettings.category_visibility }
                : {};
            items = (importedItems || []).map((it, idx) => normalizeItem(it, idx));
            if (!items.length) items = [normalizeItem({ name: "Produkt", label: "Neues Produkt", price: 0, color: fallbackColor }, 0)];
            renderList();
            renderPreview();
            renderCategoryOrder();
            syncHidden();
            if (statusEl) {
              statusEl.style.display = 'inline';
              statusEl.style.color = '#10b981';
              statusEl.textContent = 'Produkt-JSON importiert.';
              setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
            }
          };
          reader.readAsText(file);
        });
      }

      if (exportButton) {
        exportButton.addEventListener("click", () => {
          const data = {
            ...baseSettings,
            depot_price: depotPrice,
            category_order: categoryOrder,
            category_visibility: categoryVisibility,
            items,
          };
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "produkte.json";
          a.click();
          URL.revokeObjectURL(url);
        });
      }

      wrapper.productApi = {
        getSettings: () => ({
          ...baseSettings,
          depot_price: depotPrice,
          category_order: categoryOrder,
          category_visibility: categoryVisibility,
          items,
        }),
        setSettings: (data) => {
          const importedItems = Array.isArray(data && data.items) ? data.items : [];
          baseSettings = data && typeof data === "object" && !Array.isArray(data) ? { ...data } : {};
          depotPrice = normalizeDepotPrice(baseSettings.depot_price);
          categoryOrder = Array.isArray(baseSettings.category_order)
            ? baseSettings.category_order.map((name) => String(name || "").trim()).filter(Boolean)
            : [];
          categoryVisibility =
            baseSettings.category_visibility && typeof baseSettings.category_visibility === "object"
              ? { ...baseSettings.category_visibility }
              : {};
          if (depotInput) {
            depotInput.value = depotPrice;
          }
          items = importedItems.length ? importedItems.map((it, idx) => normalizeItem(it, idx)) : [normalizeItem({ name: "Produkt", label: "Produkt", price: 0, color: fallbackColor }, 0)];
          renderList();
          renderPreview();
          renderCategoryOrder();
          syncHidden();
        },
      };

        renderList();
        renderPreview();
        renderCategoryOrder();
        syncHidden();
      });
    });

    // Preisliste-Settings
    safeRun("price-settings", () => {
      document.querySelectorAll("[data-price-settings]").forEach((wrapper) => {
        const form = wrapper.closest("form");
        const sharedInput = form ? form.querySelector('input[name="shared_settings"]') : null;
        const productEditor = form ? form.querySelector("[data-product-editor]") : null;
        const defaults = { ...priceDefaults, ...parseJson(wrapper.dataset.defaults, priceDefaults) };
        const current = parseJson(wrapper.dataset.current, {});

      let shared = parseJson(sharedInput ? sharedInput.value : "", {});
      let settings = { ...defaults, ...(shared.price_list || current) };

      const normalizeSettings = (data) => {
        const next = { ...defaults, ...(data || {}) };
        next.font_size = clampNumber(next.font_size, defaults.font_size, 0.6, 6);
        next.rotation_seconds = clampNumber(next.rotation_seconds, defaults.rotation_seconds, 2, 120);
        next.background_mode = ["none", "custom"].includes(next.background_mode) ? next.background_mode : defaults.background_mode;
        next.background_color = sanitizeColor(next.background_color || defaults.background_color || fallbackColor);
        next.enabled_categories = Array.isArray(next.enabled_categories)
          ? next.enabled_categories.filter((name) => typeof name === "string" && name.trim())
          : [];
        return next;
      };

      const getItemsFromEditor = () => {
        if (productEditor && productEditor.productApi) {
          const settings = productEditor.productApi.getSettings();
          return Array.isArray(settings.items) ? settings.items : [];
        }
        const fallback = form ? form.querySelector('input[name="kassensystem_settings"]') : null;
        const parsed = parseJson(fallback ? fallback.value : "", {});
        return Array.isArray(parsed.items) ? parsed.items : [];
      };

      const getCategoryOrder = () => {
        if (productEditor && productEditor.productApi) {
          const settings = productEditor.productApi.getSettings();
          return Array.isArray(settings.category_order) ? settings.category_order : [];
        }
        const fallback = form ? form.querySelector('input[name="kassensystem_settings"]') : null;
        const parsed = parseJson(fallback ? fallback.value : "", {});
        return Array.isArray(parsed.category_order) ? parsed.category_order : [];
      };

      const getCategoryVisibility = () => {
        if (productEditor && productEditor.productApi) {
          const settings = productEditor.productApi.getSettings();
          return settings.category_visibility && typeof settings.category_visibility === "object" ? settings.category_visibility : {};
        }
        const fallback = form ? form.querySelector('input[name="kassensystem_settings"]') : null;
        const parsed = parseJson(fallback ? fallback.value : "", {});
        return parsed.category_visibility && typeof parsed.category_visibility === "object" ? parsed.category_visibility : {};
      };

      const getCategories = () => {
        const items = getItemsFromEditor();
        const categories = new Set();
        categories.add(defaultCategory);
        const visibility = getCategoryVisibility();
        items.forEach((item) => {
          if (item && item.show_in_price_list === false) return;
          const category = String(item && item.category != null ? item.category : defaultCategory).trim();
          if (visibility[category] && visibility[category].price_list === false) return;
          if (category) categories.add(category);
        });
        const ordered = [];
        const order = getCategoryOrder();
        const available = Array.from(categories);
        const seen = new Set();
        order.forEach((name) => {
          if (typeof name !== "string") return;
          const cleaned = name.trim();
          if (cleaned && categories.has(cleaned) && !seen.has(cleaned)) {
            ordered.push(cleaned);
            seen.add(cleaned);
          }
        });
        available
          .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()))
          .forEach((name) => {
            if (!seen.has(name)) ordered.push(name);
          });
        return ordered;
      };

      const updateShared = () => {
        if (!sharedInput) return;
        shared = parseJson(sharedInput.value, {});
        shared.price_list = settings;
        sharedInput.value = JSON.stringify(shared);
      };

      const errorEl = wrapper.querySelector("[data-price-error]");
      const customBg = wrapper.querySelector("[data-price-custom-bg]");
      const imageSelects = Array.from(wrapper.querySelectorAll("[data-price-image-select]"));
      const imagePreviews = Array.from(wrapper.querySelectorAll("[data-price-image-preview]"));

      const syncInputs = () => {
        wrapper.querySelectorAll("[data-price-field]").forEach((input) => {
          const key = input.dataset.priceField;
          if (!key) return;
          if (input.type === "number") {
            input.value = settings[key] ?? defaults[key] ?? "";
          } else if (input.type === "color") {
            input.value = sanitizeColor(settings[key] || defaults[key] || fallbackColor);
          } else if (input.tagName === "SELECT") {
            input.value = settings[key] ?? defaults[key] ?? "";
          }
        });
        if (customBg) {
          customBg.style.display = settings.background_mode === "custom" ? "block" : "none";
        }
        imageSelects.forEach((select) => {
          select.value = settings.background_image || "";
        });
        imagePreviews.forEach((preview) => {
          if (settings.background_image) {
            preview.src = `/uploads/${settings.background_image}`;
            preview.style.display = "block";
          } else {
            preview.removeAttribute("src");
            preview.style.display = "none";
          }
        });
      };

      const renderCategories = () => {
        const container = wrapper.querySelector("[data-price-categories]");
        if (!container) return;
        const categories = getCategories();
        const enabledRaw = settings.enabled_categories.length ? settings.enabled_categories : categories;
        const enabled = enabledRaw.filter((name) => categories.includes(name));
        settings.enabled_categories = enabled;
        container.innerHTML = "";

        categories.forEach((name) => {
          const label = document.createElement("label");
          label.style.display = "inline-flex";
          label.style.alignItems = "center";
          label.style.gap = "0.4rem";
          label.style.marginRight = "0.8rem";
          const checkbox = document.createElement("input");
          checkbox.type = "checkbox";
          checkbox.checked = enabled.includes(name);
          checkbox.addEventListener("change", () => {
            const selected = Array.from(container.querySelectorAll("input[type='checkbox']"))
              .filter((el) => el.checked)
              .map((el) => el.dataset.category || "")
              .filter(Boolean);

            settings.enabled_categories = selected;
            if (errorEl) {
              if (!selected.length) {
                errorEl.textContent = "Keine Auswahl = alle Kategorien.";
                errorEl.style.color = "#94a3b8";
                errorEl.style.display = "block";
              } else {
                errorEl.textContent = "";
                errorEl.style.display = "none";
              }
            }
            updateShared();
          });
          checkbox.dataset.category = name;
          label.appendChild(checkbox);
          const span = document.createElement("span");
          span.textContent = name;
          label.appendChild(span);
          container.appendChild(label);
        });

        if (errorEl && !settings.enabled_categories.length) {
          errorEl.textContent = "Keine Auswahl = alle Kategorien.";
          errorEl.style.color = "#94a3b8";
          errorEl.style.display = "block";
        }
      };

      wrapper.querySelectorAll("[data-price-field]").forEach((input) => {
        const key = input.dataset.priceField;
        if (!key) return;
        input.addEventListener("input", () => {
          if (input.type === "number") {
            settings[key] = clampNumber(input.value, defaults[key], key === "rotation_seconds" ? 2 : 0.6, key === "rotation_seconds" ? 120 : 6);
          } else if (input.type === "color") {
            settings[key] = sanitizeColor(input.value || defaults[key] || fallbackColor);
          } else if (input.tagName === "SELECT") {
            settings[key] = input.value;
            if (key === "background_mode" && input.value !== "custom") {
              settings.background_image = null;
            }
          }
          settings = normalizeSettings(settings);
          syncInputs();
          updateShared();
        });
      });

      if (imageSelects.length) {
        imageSelects.forEach((select) => {
          select.addEventListener("change", () => {
            const selected = select.value || "";
            settings.background_image = selected || null;
            if (selected) {
              settings.background_mode = "custom";
            }
            settings = normalizeSettings(settings);
            syncInputs();
            updateShared();
          });
        });
      }

      if (productEditor) {
        productEditor.addEventListener("product-editor:change", () => {
          renderCategories();
          updateShared();
        });
      }

      wrapper.priceSettingsApi = {
        getSettings: () => ({ ...settings }),
        setSettings: (data) => {
          settings = normalizeSettings(data);
          syncInputs();
          renderCategories();
          updateShared();
        },
      };

        settings = normalizeSettings(settings);
        syncInputs();
        renderCategories();
        updateShared();
      });
    });

    const collectSnapshot = (form) => {
      const sharedInput = form.querySelector('input[name="shared_settings"]');
      const shotInput = form.querySelector('input[name="shotcounter_settings"]');
      const productEditor = form.querySelector("[data-product-editor]");
      const shotSettingsWrapper = form.querySelector("[data-shot-settings]");
      return {
        kassensystem_enabled: Boolean((form.querySelector('[name="kassensystem_enabled"]') || {}).checked),
        shotcounter_enabled: Boolean((form.querySelector('[name="shotcounter_enabled"]') || {}).checked),
        shared_settings: parseJson(sharedInput ? sharedInput.value : "", {}),
        shotcounter_settings:
          (shotSettingsWrapper && shotSettingsWrapper.shotSettingsApi && shotSettingsWrapper.shotSettingsApi.getSettings()) ||
          parseJson(shotInput ? shotInput.value : "", {}),
        kassensystem_settings:
          (productEditor && productEditor.productApi && productEditor.productApi.getSettings()) ||
          parseJson((form.querySelector('input[name="kassensystem_settings"]') || {}).value, {}),
      };
    };

    const applySnapshot = (form, snapshot) => {
      const kassCheck = form.querySelector('[name="kassensystem_enabled"]');
      const shotCheck = form.querySelector('[name="shotcounter_enabled"]');
      if (kassCheck) kassCheck.checked = Boolean(snapshot.kassensystem_enabled);
      if (shotCheck) shotCheck.checked = Boolean(snapshot.shotcounter_enabled);

      const sharedHidden = form.querySelector('input[name="shared_settings"]');
      const shotHidden = form.querySelector('input[name="shotcounter_settings"]');
      const priceSettingsWrapper = form.querySelector("[data-price-settings]");
      if (sharedHidden) sharedHidden.value = JSON.stringify(snapshot.shared_settings || {});
      if (shotHidden) shotHidden.value = JSON.stringify(snapshot.shotcounter_settings || {});

      // Apply shared settings checkboxes
      const autoReloadCheckbox = form.querySelector('input[name="auto_reload_on_add"]');
      if (autoReloadCheckbox && snapshot.shared_settings) {
        autoReloadCheckbox.checked = snapshot.shared_settings.auto_reload_on_add !== false; // default to true
      }

      const productEditor = form.querySelector("[data-product-editor]");
      const kassInput = form.querySelector('input[name="kassensystem_settings"]');
      const shotSettingsWrapper = form.querySelector("[data-shot-settings]");
      if (shotSettingsWrapper && shotSettingsWrapper.shotSettingsApi) {
        shotSettingsWrapper.shotSettingsApi.setSettings(snapshot.shotcounter_settings || {});
      }
      if (priceSettingsWrapper && priceSettingsWrapper.priceSettingsApi) {
        const shared = snapshot.shared_settings || {};
        priceSettingsWrapper.priceSettingsApi.setSettings(shared.price_list || {});
      }
      if (productEditor && productEditor.productApi) {
        productEditor.productApi.setSettings(snapshot.kassensystem_settings || { items: defaultButtons });
      } else if (kassInput) {
        kassInput.value = JSON.stringify(snapshot.kassensystem_settings || { items: defaultButtons });
      }
    };

    const bindCopyAndImport = (form) => {
      const select = form.querySelector("[data-copy-select]");
      const copyBtn = form.querySelector("[data-copy-btn]");
      const importTrigger = form.querySelector("[data-import-event]");
      const exportBtn = form.querySelector("[data-export-event]");
      const statusEl = form.querySelector('[data-form-status]');

      if (copyBtn) {
        copyBtn.addEventListener("click", () => {
          const selectedId = select ? select.value : null;
          if (!selectedId || !eventData[selectedId]) return;
          applySnapshot(form, eventData[selectedId]);
        });
      }

      if (exportBtn) {
        exportBtn.addEventListener("click", () => {
          const data = collectSnapshot(form);
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = "event-settings.json";
          a.click();
          URL.revokeObjectURL(url);
        });
      }

      if (importTrigger) {
        importTrigger.addEventListener("change", (ev) => {
          const file = ev.target.files && ev.target.files[0];
          if (!file) return;
          const reader = new FileReader();
          reader.onload = () => {
            const data = parseJson(reader.result, null);
            if (!data) {
              if (statusEl) {
                statusEl.style.display = 'inline';
                statusEl.style.color = '#ef4444';
                statusEl.textContent = 'Fehler: Event-JSON konnte nicht gelesen werden.';
                setTimeout(() => { statusEl.style.display = 'none'; }, 4000);
              }
              return;
            }
            applySnapshot(form, {
              kassensystem_enabled: data.kassensystem_enabled !== undefined ? data.kassensystem_enabled : true,
              shotcounter_enabled: data.shotcounter_enabled !== undefined ? data.shotcounter_enabled : true,
              shared_settings: data.shared_settings || {},
              shotcounter_settings: data.shotcounter_settings || {},
              kassensystem_settings: data.kassensystem_settings || { items: defaultButtons },
            });
            if (statusEl) {
              statusEl.style.display = 'inline';
              statusEl.style.color = '#10b981';
              statusEl.textContent = 'Event-JSON importiert.';
              setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
            }
          };
          reader.readAsText(file);
        });
      }
    };

    safeRun("event-form", () => {
      document.querySelectorAll("[data-event-form]").forEach((form) => {
        bindCopyAndImport(form);

      // Ensure submit button works properly
      const submitBtn = form.querySelector('[data-submit-btn]');
      if (submitBtn) {
        submitBtn.addEventListener('click', function(e) {
          // Let the button naturally submit the form
          // This click handler is just to ensure the form is properly prepared
          const statusEl = form.querySelector('[data-form-status]');

          // Validate product names are unique before submission
          const productEditor = form.querySelector('[data-product-editor]');
          if (productEditor && productEditor.productApi) {
            const settings = productEditor.productApi.getSettings();
            const items = settings.items || [];
            const names = items.map(item => item.name);
            const duplicates = names.filter((name, index) => names.indexOf(name) !== index);

            if (duplicates.length > 0) {
              e.preventDefault();
              e.stopPropagation();
              if (statusEl) {
                statusEl.style.display = 'inline';
                statusEl.style.color = '#ef4444';
                statusEl.textContent = `Fehler: Doppelte Produktnamen gefunden: ${duplicates.join(', ')}`;
                setTimeout(() => {
                  statusEl.style.display = 'none';
                }, 5000);
              }
              alert(`Fehler: Doppelte Produktnamen gefunden: ${duplicates.join(', ')}`);
              return false;
            }
          }

          const priceSettingsWrapper = form.querySelector("[data-price-settings]");
          if (priceSettingsWrapper && priceSettingsWrapper.priceSettingsApi) {
            priceSettingsWrapper.priceSettingsApi.getSettings();
          }
        });
      }

      // Add submit handler to collect shared settings from checkboxes and show loading state
        form.addEventListener('submit', function(e) {
        const submitBtn = this.querySelector('[data-submit-btn]');
        const statusEl = this.querySelector('[data-form-status]');

        // Show loading state
        if (submitBtn) {
          submitBtn.disabled = true;
          const originalText = submitBtn.textContent;
          submitBtn.textContent = 'Speichere...';
          submitBtn.dataset.originalText = originalText;
        }
        if (statusEl) {
          statusEl.style.display = 'inline';
          statusEl.style.color = '#94a3b8';
          statusEl.textContent = 'Daten werden gespeichert...';
        }

        // Collect shared settings
        const sharedInput = this.querySelector('input[name="shared_settings"]');
        if (sharedInput) {
          const currentSettings = parseJson(sharedInput.value, {});

          // Collect all checkboxes with data-shared-setting attribute
          const autoReloadCheckbox = this.querySelector('input[name="auto_reload_on_add"]');
          if (autoReloadCheckbox) {
            currentSettings.auto_reload_on_add = autoReloadCheckbox.checked;
          }

          const priceSettingsWrapper = this.querySelector("[data-price-settings]");
          if (priceSettingsWrapper && priceSettingsWrapper.priceSettingsApi) {
            currentSettings.price_list = priceSettingsWrapper.priceSettingsApi.getSettings();
          }

          sharedInput.value = JSON.stringify(currentSettings);
        }

        // Form will now submit naturally
        });
      });
    });

    safeRun("credentials", () => {
      const credentialsForm = document.querySelector("[data-credentials-form]");
      if (credentialsForm) {
        const errorBox = credentialsForm.querySelector("[data-credentials-error]");
        const usernameInput = credentialsForm.querySelector("#admin_username");
        const passwordInput = credentialsForm.querySelector("#admin_password");
        const hasPassword = credentialsForm.dataset.hasPassword === "true";

        const showError = (message) => {
          if (!errorBox) return;
          errorBox.textContent = message;
          errorBox.style.display = "block";
        };

        const clearError = () => {
          if (!errorBox) return;
          errorBox.textContent = "";
          errorBox.style.display = "none";
        };

        credentialsForm.addEventListener("submit", (event) => {
          const username = (usernameInput?.value || "").trim();
          const password = (passwordInput?.value || "").trim();

          if (!username) {
            event.preventDefault();
            showError("Benutzername darf nicht leer sein.");
            return;
          }

          if (!hasPassword && !password) {
            event.preventDefault();
            showError("Bitte ein Passwort setzen, damit der Admin-Bereich geschützt ist.");
            return;
          }

          if (password && password.length < 8) {
            event.preventDefault();
            showError("Passwort muss mindestens 8 Zeichen lang sein.");
            return;
          }

          clearError();
        });
      }
    });

  // Network Management UI
  const loadNetworkStatus = async () => {
    const container = document.getElementById('network-status');
    if (!container) return;

    try {
      const response = await fetch('/admin/network');
      const data = await response.json();

      let html = '<div style="display: grid; gap: 1.5rem;">';

      // LAN (eth0) Section
      html += '<div class="stack">';
      html += '<h3 style="margin: 0; color: #cbd5e1;">LAN Interface (eth0)</h3>';
      if (data.eth0.exists) {
        html += '<div style="background: rgba(255,255,255,0.04); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">';
        html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>IP-Adresse:</strong> <span>${data.eth0.ip || 'N/A'}</span></div>`;
        html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>Subnetzmaske:</strong> <span>${data.eth0.netmask || 'N/A'}</span></div>`;
        html += `<div class="field-inline"><strong>Status:</strong> <span class="badge ${data.eth0.status === 'up' ? 'badge-green' : 'badge-red'}">${data.eth0.status}</span></div>`;
        html += '</div>';
      } else {
        html += '<p class="muted">Interface nicht gefunden</p>';
      }
      html += '</div>';

      // WLAN (wlan0) Section
      html += '<div class="stack">';
      html += '<h3 style="margin: 0; color: #cbd5e1;">WLAN Interface (wlan0)</h3>';
      if (data.wlan0.exists) {
        html += '<div style="background: rgba(255,255,255,0.04); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">';
        html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>IP-Adresse:</strong> <span>${data.wlan0.ip || 'Nicht verbunden'}</span></div>`;
        html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>SSID:</strong> <span>${data.wlan0.ssid || 'Nicht verbunden'}</span></div>`;
        if (data.wlan0.signal_level) {
          html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>Signalstärke:</strong> <span>${data.wlan0.signal_level}</span></div>`;
        }
        html += `<div class="field-inline"><strong>Status:</strong> <span class="badge ${data.wlan0.status === 'up' ? 'badge-green' : 'badge-red'}">${data.wlan0.status}</span></div>`;
        html += '</div>';

        // WiFi Connect Form
        html += '<div style="margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border); border-radius: 8px;">';
        html += '<h4 style="margin: 0 0 0.8rem 0;">Neues WLAN verbinden</h4>';
        html += '<form id="wifi-connect-form">';
        html += '<div class="stack" style="margin-bottom: 0.8rem;">';
        html += '<label>SSID (Netzwerkname)</label>';
        html += '<input type="text" name="ssid" required placeholder="Netzwerkname eingeben">';
        html += '</div>';
        html += '<div class="stack" style="margin-bottom: 0.8rem;">';
        html += '<label>Passwort</label>';
        html += '<input type="password" name="password" placeholder="Passwort (min. 8 Zeichen)">';
        html += '</div>';
        html += '<div class="field-inline">';
        html += '<button type="submit">Verbinden</button>';
        html += '<button type="button" onclick="scanWifi()" class="secondary">Netzwerke scannen</button>';
        html += '</div>';
        html += '<div id="wifi-connect-message" style="margin-top: 0.8rem;"></div>';
        html += '</form>';
        html += '<div id="wifi-scan-results" style="margin-top: 1rem;"></div>';
        html += '</div>';
      } else {
        html += '<p class="muted">Interface nicht gefunden</p>';
      }
      html += '</div>';

      // DHCP Leases Section
      html += '<div class="stack">';
      html += '<h3 style="margin: 0; color: #cbd5e1;">Verbundene Clients (DHCP)</h3>';
      if (data.dhcp_leases && data.dhcp_leases.length > 0) {
        html += '<div style="background: rgba(255,255,255,0.04); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">';
        html += '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="border-bottom: 1px solid var(--border);"><th style="text-align: left; padding: 0.5rem;">IP</th><th style="text-align: left; padding: 0.5rem;">MAC</th><th style="text-align: left; padding: 0.5rem;">Hostname</th></tr></thead>';
        html += '<tbody>';
        data.dhcp_leases.forEach(lease => {
          html += `<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);"><td style="padding: 0.5rem;">${lease.ip}</td><td style="padding: 0.5rem; font-family: monospace;">${lease.mac}</td><td style="padding: 0.5rem;">${lease.hostname}</td></tr>`;
        });
        html += '</tbody></table>';
        html += '</div>';
      } else {
        html += '<p class="muted">Keine verbundenen Clients</p>';
      }
      html += '</div>';

      html += '</div>';

      container.innerHTML = html;

      // Attach WiFi connect handler
      const wifiForm = document.getElementById('wifi-connect-form');
      if (wifiForm) {
        wifiForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const formData = new FormData(e.target);
          const messageDiv = document.getElementById('wifi-connect-message');
          messageDiv.innerHTML = '<p class="muted">Verbinde...</p>';

          try {
            const response = await fetch('/admin/network/wifi/connect', {
              method: 'POST',
              body: formData
            });
            const result = await response.json();

            if (result.success) {
              messageDiv.innerHTML = `<p style="color: #10b981;">${result.message}</p>`;
              setTimeout(() => loadNetworkStatus(), 5000);
            } else {
              messageDiv.innerHTML = `<p style="color: #ef4444;">Fehler: ${result.error}</p>`;
            }
          } catch (error) {
            messageDiv.innerHTML = `<p style="color: #ef4444;">Fehler: ${error.message}</p>`;
          }
        });
      }
    } catch (error) {
      container.innerHTML = `<p style="color: #ef4444;">Fehler beim Laden: ${error.message}</p>`;
    }
  };

  window.scanWifi = async () => {
    const resultsDiv = document.getElementById('wifi-scan-results');
    if (!resultsDiv) return;

    resultsDiv.innerHTML = '<p class="muted">Scanne nach Netzwerken...</p>';

    try {
      const response = await fetch('/admin/network/wifi/scan');
      const data = await response.json();

      if (data.success && data.networks.length > 0) {
        let html = '<h4 style="margin: 0.8rem 0;">Verfügbare Netzwerke</h4>';
        html += '<div style="display: flex; flex-direction: column; gap: 0.5rem;">';
        data.networks.forEach(network => {
          const escapedSsid = network.ssid.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
          const ssidForJs = network.ssid.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
          html += `<div style="padding: 0.6rem; background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 6px; cursor: pointer;" onclick="document.querySelector('input[name=ssid]').value='${ssidForJs}'">`;
          html += `<div style="display: flex; justify-content: space-between; align-items: center;">`;
          html += `<strong>${escapedSsid}</strong>`;
          html += `<div style="display: flex; gap: 0.5rem; align-items: center;">`;
          html += `<span class="pill">${network.encryption}</span>`;
          html += `<span class="muted" style="font-size: 0.85rem;">${network.quality}%</span>`;
          html += `</div></div></div>`;
        });
        html += '</div>';
        resultsDiv.innerHTML = html;
      } else {
        resultsDiv.innerHTML = '<p class="muted">Keine Netzwerke gefunden</p>';
      }
    } catch (error) {
      resultsDiv.innerHTML = `<p style="color: #ef4444;">Fehler: ${error.message}</p>`;
    }
  };

  // Git Status UI
  const loadGitStatus = async () => {
    const container = document.getElementById('git-status');
    if (!container) return;

    try {
      const response = await fetch('/admin/system/git-status');
      let data;
      const ct = (response.headers.get('content-type') || '').toLowerCase();
      if (ct.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        throw new Error(`Unerwartete Server-Antwort: ${text}`);
      }

      let html = '<div class="stack">';
      html += '<div style="background: rgba(255,255,255,0.04); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">';
      html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>Branch:</strong> <span>${data.branch || 'N/A'}</span></div>`;
      html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>Commit:</strong> <span style="font-family: monospace;">${data.commit_short || 'N/A'}</span></div>`;
      html += `<div class="field-inline" style="margin-bottom: 0.5rem;"><strong>Nicht committete Änderungen:</strong> <span class="badge ${data.has_changes ? 'badge-red' : 'badge-green'}">${data.has_changes ? 'Ja' : 'Nein'}</span></div>`;

      if (data.behind > 0) {
        html += `<div class="field-inline"><strong>Status:</strong> <span class="badge badge-yellow">${data.behind} Commit(s) hinter Remote</span></div>`;
      } else {
        html += `<div class="field-inline"><strong>Status:</strong> <span class="badge badge-green">Aktuell</span></div>`;
      }
      html += '</div>';

      html += '<div style="margin-top: 1rem; padding: 1rem; background: rgba(255,255,255,0.02); border: 1px dashed var(--border); border-radius: 8px;">';
      html += '<h4 style="margin: 0 0 0.8rem 0;">Repository aktualisieren</h4>';
      html += '<p class="muted" style="margin-bottom: 0.8rem;">Lädt die neueste Version vom Git-Repository und startet den Service neu.</p>';

      if (data.has_changes) {
        html += '<p style="color: #f59e0b; margin-bottom: 0.8rem;"><strong>⚠️ Warnung:</strong> Es gibt nicht committete Änderungen. Update ist nicht möglich.</p>';
        html += '<button type="button" class="secondary" disabled>Update nicht möglich</button>';
      } else {
        html += '<button type="button" onclick="performGitUpdate()" class="primary">Jetzt aktualisieren</button>';
      }
      html += '<div id="git-update-message" style="margin-top: 0.8rem;"></div>';
      html += '</div>';

      html += '</div>';

      container.innerHTML = html;
    } catch (error) {
      container.innerHTML = `<p style="color: #ef4444;">Fehler beim Laden: ${error.message}</p>`;
    }
  };

  window.performGitUpdate = async () => {
    const messageDiv = document.getElementById('git-update-message');
    if (!messageDiv) return;

    if (!confirm('Möchten Sie wirklich das System aktualisieren? Der Service wird dabei neu gestartet.')) {
      return;
    }

    messageDiv.innerHTML = '<p class="muted">Update wird durchgeführt...</p>';

    try {
      const response = await fetch('/admin/system/git-update', {
        method: 'POST'
      });
      let result;
      const ct = (response.headers.get('content-type') || '').toLowerCase();
      if (ct.includes('application/json')) {
        result = await response.json();
      } else {
        const text = await response.text();
        messageDiv.innerHTML = `<p style="color: #ef4444;">Fehler: Unerwartete Antwort vom Server: ${text}</p>`;
        return;
      }

      if (result.success) {
        messageDiv.innerHTML = `<p style="color: #10b981;">${result.message}</p>`;
        setTimeout(() => {
          messageDiv.innerHTML += '<p class="muted">Seite wird in 5 Sekunden neu geladen...</p>';
          setTimeout(() => location.reload(), 5000);
        }, 2000);
      } else {
        messageDiv.innerHTML = `<p style="color: #ef4444;">Fehler: ${result.error}</p>`;
      }
    } catch (error) {
      messageDiv.innerHTML = `<p style="color: #ef4444;">Fehler: ${error.message}</p>`;
    }
  };

  // Load network and git status when sections are opened
  document.querySelectorAll('[data-collapsible]').forEach(collapsible => {
    const toggle = collapsible.querySelector('[data-toggle]');
    const content = collapsible.querySelector('.collapsible__content');

    if (toggle && content) {
      toggle.addEventListener('click', () => {
        // Load data when section is opened
        if (content.hidden === false) {
          if (collapsible.querySelector('#network-status')) {
            loadNetworkStatus();
          } else if (collapsible.querySelector('#git-status')) {
            loadGitStatus();
          }
        }
      });
    }
  });
})();
