"use strict";
/* Güvenli DOM üretimi: metinler hiçbir zaman HTML olarak yorumlanmaz. */
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  const p = props || {};
  for (const [k, v] of Object.entries(p)) {
    if (v == null || v === false || k === "value") continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...kids.flat(Infinity).filter((x) => x != null && x !== false));
  if ("value" in p && p.value != null) el.value = p.value;
  return el;
}

const GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const TURLER = { evci: "Evci", mazeret: "Mazeret", saglik: "Sağlık", ozel: "Özel" };

function zamanYaz(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
}
function tarihYaz(iso) {
  return iso ? new Date(iso).toLocaleDateString("tr-TR", { dateStyle: "long" }) : "";
}
function saatYaz(iso) {
  return iso ? new Date(iso).toLocaleTimeString("tr-TR", { timeStyle: "short" }) : "";
}
