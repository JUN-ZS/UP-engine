"use strict";

(function () {
  const $ = (id) => document.getElementById(id);
  const state = {
    image: null,
    imageName: "",
    objectUrl: null,
    width: 0,
    height: 0,
    draft: [],
    regions: [],
    relations: []
  };

  const canvas = $("imageCanvas");
  const ctx = canvas.getContext("2d");
  function status(message, isError) {
    $("status").textContent = message;
    $("status").classList.toggle("error", Boolean(isError));
  }

  function updateControls() {
    const hasImage = Boolean(state.image);
    $("undoPoint").disabled = state.draft.length === 0;
    $("cancelPolygon").disabled = state.draft.length === 0;
    $("finishPolygon").disabled = state.draft.length < 3;
    $("exportRegions").disabled = !hasImage || state.regions.length === 0;
    $("exportRelations").disabled = !hasImage || state.relations.length === 0;
    $("addRelation").disabled = state.regions.length < 2;
    $("relationSubject").disabled = state.regions.length < 2;
    $("relationObject").disabled = state.regions.length < 2;
    $("pointInfo").textContent = state.draft.length + " 個繪製點";
    $("regionEmpty").hidden = state.regions.length > 0;
  }

  function createOption(value, text) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = text;
    return option;
  }

  function refreshRegionSelects() {
    const selects = [$("relationSubject"), $("relationObject"), $("evidenceRegion")];
    selects.forEach((select) => {
      const previous = select.value;
      select.replaceChildren();
      select.appendChild(createOption("", "選擇區域…"));
      state.regions.forEach((region) => {
        select.appendChild(createOption(region.id, region.id + " · " + region.semantic_type));
      });
      if (state.regions.some((region) => region.id === previous)) select.value = previous;
    });
    updateControls();
  }

  function colorFor(region) {
    if (region.permission === "editable") return "rgba(22,199,132,0.28)";
    if (region.tags.includes("context")) return "rgba(84,156,255,0.22)";
    return "rgba(255,100,110,0.22)";
  }

  function drawPolygon(points, fill, stroke, close) {
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i += 1) ctx.lineTo(points[i][0], points[i][1]);
    if (close) ctx.closePath();
    if (fill) {
      ctx.fillStyle = fill;
      ctx.fill();
    }
    ctx.strokeStyle = stroke;
    ctx.lineWidth = Math.max(2, Math.min(state.width, state.height) / 500);
    ctx.stroke();
    points.forEach((point) => {
      ctx.beginPath();
      ctx.arc(point[0], point[1], Math.max(3, Math.min(state.width, state.height) / 250), 0, Math.PI * 2);
      ctx.fillStyle = stroke;
      ctx.fill();
    });
  }

  function redraw() {
    if (!state.image) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(state.image, 0, 0, state.width, state.height);
    state.regions.forEach((region) => {
      const points = region.polygon.map((p) => [p[0] * (state.width - 1), p[1] * (state.height - 1)]);
      drawPolygon(points, colorFor(region),
        region.permission === "editable" ? "#16c784" : "#ff646e", true);
      const first = points[0];
      ctx.font = "bold " + Math.max(12, Math.min(state.width, state.height) / 55) + "px sans-serif";
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#081018";
      ctx.lineWidth = 3;
      ctx.strokeText(region.id, first[0] + 5, first[1] - 6);
      ctx.fillText(region.id, first[0] + 5, first[1] - 6);
    });
    if (state.draft.length) {
      const points = state.draft.map((p) => [p[0] * (state.width - 1), p[1] * (state.height - 1)]);
      drawPolygon(points, state.draft.length >= 3 ? "rgba(255,190,53,0.12)" : null, "#ffbe35", false);
    }
  }

  function renderRegions() {
    const list = $("regionList");
    list.replaceChildren();
    state.regions.forEach((region) => {
      const li = document.createElement("li");
      const main = document.createElement("div");
      main.className = "item-main";
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = region.id;
      const pill = document.createElement("span");
      pill.className = "permission-pill " + region.permission;
      pill.textContent = region.permission;
      title.appendChild(pill);
      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = region.semantic_type + (region.tags.length ? " · " + region.tags.join(", ") : "");
      main.append(title, meta);
      const remove = document.createElement("button");
      remove.className = "secondary";
      remove.textContent = "刪除";
      remove.addEventListener("click", () => {
        state.regions = state.regions.filter((item) => item.id !== region.id);
        state.relations = state.relations.filter((relation) =>
          relation.subject_region_id !== region.id &&
          relation.object_region_id !== region.id &&
          relation.evidence_region_id !== region.id
        );
        renderAll();
      });
      li.append(main, remove);
      list.appendChild(li);
    });
    refreshRegionSelects();
    redraw();
  }

  function renderRelations() {
    const list = $("relationList");
    list.replaceChildren();
    state.relations.forEach((relation) => {
      const li = document.createElement("li");
      const main = document.createElement("div");
      main.className = "item-main";
      const title = document.createElement("div");
      title.className = "item-title";
      title.textContent = relation.subject_region_id + " " + relation.predicate + " " + relation.object_region_id;
      const meta = document.createElement("div");
      meta.className = "item-meta";
      meta.textContent = relation.status + " · " + relation.source +
        (relation.evidence_region_id ? " · evidence: " + relation.evidence_region_id : "");
      main.append(title, meta);
      const remove = document.createElement("button");
      remove.className = "secondary";
      remove.textContent = "刪除";
      remove.addEventListener("click", () => {
        state.relations = state.relations.filter((item) => item.id !== relation.id);
        renderAll();
      });
      li.append(main, remove);
      list.appendChild(li);
    });
    updateControls();
  }

  function renderAll() {
    renderRegions();
    renderRelations();
    updateControls();
  }

  function defaultRegionId() {
    const seed = ($("semanticType").value || "region").toLowerCase().replace(/[^a-z0-9_.-]+/g, "-").replace(/^-+|-+$/g, "");
    const base = seed || "region";
    let candidate = base;
    let index = 2;
    while (state.regions.some((region) => region.id === candidate)) {
      candidate = base + "-" + index;
      index += 1;
    }
    return candidate;
  }

  function openRegionEditor() {
    $("regionEditor").hidden = false;
    $("regionId").dataset.userEdited = "";
    $("regionLabel").value = "";
    $("semanticType").value = "unknown";
    $("permission").value = "protected";
    $("regionTags").value = "object";
    $("regionId").value = defaultRegionId();
    $("regionLabel").focus();
  }

  function saveRegion() {
    const id = $("regionId").value.trim();
    const label = $("regionLabel").value.trim();
    const semanticType = $("semanticType").value.trim();
    if (!/^[A-Za-z0-9_.-]+$/.test(id)) {
      status("Region ID 只可使用英文字母、數字、點、底線和連字號。", true);
      return;
    }
    if (!label || !semanticType) {
      status("顯示名稱與 semantic_type 均不可留空。", true);
      return;
    }
    if (state.regions.some((region) => region.id === id)) {
      status("Region ID 已存在，請使用唯一 ID。", true);
      return;
    }
    const points = state.draft.map((p) => p.slice());
    if (points.length < 3) {
      status("多邊形至少需要三個點。", true);
      return;
    }
    const tags = $("regionTags").value.split(",").map((tag) => tag.trim()).filter(Boolean);
    if (new Set(tags).size !== tags.length) {
      status("Tags 不可重複。", true);
      return;
    }
    state.regions.push({
      id,
      label,
      semantic_type: semanticType,
      permission: $("permission").value,
      tags,
      polygon: points
    });
    state.draft = [];
    $("regionEditor").hidden = true;
    status("已加入 Region：" + id + "。請再檢查遮罩與權限。");
    renderAll();
  }

  function addRelation() {
    const subject = $("relationSubject").value;
    const objectId = $("relationObject").value;
    const predicate = $("relationPredicate").value;
    const relationStatus = $("relationStatus").value;
    const source = $("relationSource").value;
    const evidence = $("relationEvidence").value.trim();
    const confidenceText = $("relationConfidence").value.trim();
    const evidenceRegion = $("evidenceRegion").value || null;
    if (!subject || !objectId || subject === objectId) {
      status("請選擇兩個不同的 Subject / Object Region。", true);
      return;
    }
    if (relationStatus === "human_verified" && (source !== "human" || !evidence)) {
      status("human_verified 必須由 human 提供，並填寫可檢查的 evidence。", true);
      return;
    }
    if (relationStatus === "candidate" && source === "model" && !evidence) {
      status("Model candidate 必須記錄模型觀察或輸出證據。", true);
      return;
    }
    let confidence = null;
    if (confidenceText) {
      confidence = Number(confidenceText);
      if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
        status("Confidence 必須介乎 0 至 1，或留空。", true);
        return;
      }
    }
    const details = {};
    if (predicate === "contacts_at") {
      const subjectSurface = $("subjectSurface").value.trim();
      const objectSurface = $("objectSurface").value.trim();
      if (!subjectSurface || !objectSurface) {
        status("contacts_at 必須填寫 subject_surface 和 object_surface。", true);
        return;
      }
      details.subject_surface = subjectSurface;
      details.object_surface = objectSurface;
    }
    const idBase = (subject + "-" + predicate + "-" + objectId).toLowerCase().replace(/[^a-z0-9_.-]+/g, "-");
    let id = idBase;
    let suffix = 2;
    while (state.relations.some((item) => item.id === id)) {
      id = idBase + "-" + suffix;
      suffix += 1;
    }
    state.relations.push({
      id,
      subject_region_id: subject,
      predicate,
      object_region_id: objectId,
      status: relationStatus,
      source,
      confidence,
      evidence,
      evidence_region_id: evidenceRegion,
      details
    });
    $("relationEvidence").value = "";
    status("已加入 Relation：" + id + "。候選關係仍需人工確認。");
    renderRelations();
  }

  function downloadJson(filename, payload) {
    const blob = new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  $("imageFile").addEventListener("change", (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (state.objectUrl) URL.revokeObjectURL(state.objectUrl);
    state.objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      state.image = image;
      state.imageName = file.name;
      state.width = image.naturalWidth;
      state.height = image.naturalHeight;
      state.regions = [];
      state.relations = [];
      state.draft = [];
      canvas.width = state.width;
      canvas.height = state.height;
      canvas.hidden = false;
      $("emptyState").hidden = true;
      $("imageInfo").textContent = file.name + " · " + state.width + " × " + state.height;
      status("圖片已載入。請按圖點選多邊形座標。原圖不會被修改或上傳。");
      renderAll();
    };
    image.onerror = () => status("無法讀取此圖片格式。", true);
    image.src = state.objectUrl;
  });

  canvas.addEventListener("click", (event) => {
    if (!state.image || $("regionEditor").hidden === false) return;
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(0, Math.min(state.width - 1, (event.clientX - rect.left) * state.width / rect.width));
    const y = Math.max(0, Math.min(state.height - 1, (event.clientY - rect.top) * state.height / rect.height));
    state.draft.push([Number((x / Math.max(1, state.width - 1)).toFixed(7)),
                      Number((y / Math.max(1, state.height - 1)).toFixed(7))]);
    redraw();
    updateControls();
  });

  $("undoPoint").addEventListener("click", () => {
    state.draft.pop();
    redraw();
    updateControls();
  });
  $("cancelPolygon").addEventListener("click", () => {
    state.draft = [];
    redraw();
    updateControls();
  });
  $("finishPolygon").addEventListener("click", () => {
    if (state.draft.length < 3) return;
    openRegionEditor();
  });
  $("saveRegion").addEventListener("click", saveRegion);
  $("discardRegion").addEventListener("click", () => {
    $("regionEditor").hidden = true;
    state.draft = [];
    redraw();
    updateControls();
  });
  $("semanticType").addEventListener("input", () => {
    if ($("regionEditor").hidden === false && !$("regionId").dataset.userEdited) {
      $("regionId").value = defaultRegionId();
    }
  });
  $("regionId").addEventListener("input", () => { $("regionId").dataset.userEdited = "true"; });
  $("relationPredicate").addEventListener("change", () => {
    const isContact = $("relationPredicate").value === "contacts_at";
    $("subjectSurfaceWrap").hidden = !isContact;
    $("objectSurfaceWrap").hidden = !isContact;
  });
  $("addRelation").addEventListener("click", addRelation);
  $("exportRegions").addEventListener("click", () => {
    downloadJson("read_regions.json", { coordinate_space: "normalized_0_1", regions: state.regions });
    status("已匯出 read_regions.json。");
  });
  $("exportRelations").addEventListener("click", () => {
    downloadJson("read_relations.json", { version: "0.1.0", relations: state.relations });
    status("已匯出 read_relations.json。");
  });

  updateControls();
})();
