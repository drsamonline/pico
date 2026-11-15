// minimal DOM so the console script can boot outside a browser
function el(id){
  const o = {
    id, dataset:{}, style:{}, value:"", textContent:"", innerHTML:"", placeholder:"",
    children:[], classList:{add(){},remove(){},toggle(){},contains(){return false}},
    appendChild(c){this.children.push(c); return c},
    prepend(c){this.children.unshift(c); return c},
    insertBefore(c){this.children.unshift(c); return c},
    remove(){}, focus(){}, blur(){}, click(){}, addEventListener(){}, removeEventListener(){},
    querySelector(){return el("q")}, querySelectorAll(){return []},
    setAttribute(){}, getAttribute(){return null}, scrollIntoView(){}, closest(){return el("c")},
    cloneNode(){return el("n")}, contains(){return false}, matches(){return false},

  };
  Object.defineProperty(o, "parentElement", {get(){ return o.__p || (o.__p = el("parent")); }});
  Object.defineProperty(o, "firstChild",   {get(){ return o.__f || (o.__f = el("first")); }});
  Object.defineProperty(o, "lastChild",    {get(){ return o.__l || (o.__l = el("last")); }});
  return o;
}
const cache = {};
document = {
  querySelector(sel){ cache[sel] = cache[sel] || el(sel); return cache[sel]; },
  getElementById(id){ cache["#"+id] = cache["#"+id] || el(id); return cache["#"+id]; },
  createElement(){ return el("new"); },
  createDocumentFragment(){ return el("frag"); },
  addEventListener(){}, body: el("body"), documentElement: el("html"),
  execCommand(){return true}, querySelectorAll(){ return []; },
};
window = {
  innerWidth: 1440, addEventListener(){}, matchMedia(){return {matches:false, addEventListener(){}}},
  location:{hash:"", protocol:"file:", reload(){}}, navigator:{userAgent:"node", serviceWorker:null},
  setTimeout, clearTimeout, setInterval, clearInterval, fetch:null,
};
localStorage = {
  _d:{}, getItem(k){return this._d[k] ?? null}, setItem(k,v){this._d[k]=String(v)},
  removeItem(k){delete this._d[k]}, clear(){this._d={}},
};
navigator = window.navigator;
location = window.location;
matchMedia = window.matchMedia;

