/**
 * pet-dress —— 给 dsh-pet 加右键「换装」，并自带四套衣服
 *
 * 做三件事：
 *   0. 先确认 dsh-pet 在线（GET /dsh-pet-7340/state）；没装就什么都不做，
 *      不往它的目录写东西、也不注册菜单。
 *   1. 首次启动（或素材缺失时）把自带的 pets/ 装进 ~/.dsh/dsh-pet/pet/：
 *      缺哪套补哪套；已有的 config 不覆盖（用户可能改过名字），也不删别人的。
 *   2. 扫描 pet/ 与主配置里的所有宠物实例，注册右键菜单「换装：<衣服名>」；
 *      点哪项就把那只设成显示、其余收起（走 POST /pet-display）。
 *
 * 不碰 dsh-pet 的任何代码，只走它的公开 HTTP 接口 + 它自己的 pet/ 目录约定。
 * 菜单注册：POST /dsh-pet-7340/menu/item      { owner, labels, target }
 * 点击事件：GET  /dsh-pet-7340/menu/events?owner=... （读取即消费）
 * 切显示：  POST /dsh-pet-7340/pet-display     { id, display }
 */
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const OWNER = 'pet-dress';
const VERSION = '0.1.0';
const DSH_HOME = process.env.DSH_HOME || join(homedir(), '.dsh');
const PET_DIR = join(DSH_HOME, 'dsh-pet', 'pet');
const MAIN_CONFIG = join(DSH_HOME, 'dsh-pet', 'main-config.jsonc');
/** 插件自己的配置：{ "mode": "single" } —— single=换装（互斥），multi=每只单独开关 */
const PLUGIN_DIR = join(DSH_HOME, 'pet-dress');
const WARDROBE_CONFIG = join(PLUGIN_DIR, 'config.json');
const INSTALL_STATE = join(PLUGIN_DIR, 'installed.json');
/** 插件包里自带的四套衣服 */
const BUNDLED_PETS = join(dirname(fileURLToPath(import.meta.url)), 'pets');

/** JSONC 去注释（够用即可：行注释 + 块注释）。 */
const stripJsonc = (text) => text.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');

function readJsonc(path) {
  try {
    const raw = JSON.parse(stripJsonc(readFileSync(path, 'utf8')));
    return raw && typeof raw === 'object' ? raw : null;
  } catch {
    return null;
  }
}

/** 读模式：默认 single（换装，一次穿一套）；multi 时每只单独开关。 */
function readMode() {
  const cfg = readJsonc(WARDROBE_CONFIG);
  return cfg?.mode === 'multi' ? 'multi' : 'single';
}

/**
 * 把自带的四套衣服装进 pet/ 目录。
 * 规则：config 缺了才拷（已存在=用户可能改过名字，保留）；素材缺了才补（不覆盖用户替换过的文件）。
 */
export function installPacks(log) {
  const result = { installed: [], kept: [], copiedFiles: 0 };
  if (!existsSync(BUNDLED_PETS)) {
    log('包里没有 pets/，跳过装机');
    return result;
  }
  const kinds = readdirSync(BUNDLED_PETS)
    .filter((f) => /-config\.json$/.test(f))
    .map((f) => f.replace(/-config\.json$/, ''))
    .sort();

  try {
    mkdirSync(PET_DIR, { recursive: true });
  } catch (err) {
    log('建不了 pet/ 目录，跳过装机：' + err.message);
    return result;
  }

  for (const kind of kinds) {
    const srcCfg = join(BUNDLED_PETS, `${kind}-config.json`);
    const dstCfg = join(PET_DIR, `${kind}-config.json`);
    if (existsSync(dstCfg)) {
      result.kept.push(kind);
    } else {
      try {
        copyFileSync(srcCfg, dstCfg);
        result.installed.push(kind);
      } catch (err) {
        log(`复制 ${kind}-config.json 失败：${err.message}`);
      }
    }

    const srcAnim = join(BUNDLED_PETS, `${kind}-animation`);
    if (!existsSync(srcAnim)) continue;
    const dstAnim = join(PET_DIR, `${kind}-animation`);
    try {
      mkdirSync(dstAnim, { recursive: true });
    } catch {
      continue;
    }
    for (const file of readdirSync(srcAnim)) {
      const dst = join(dstAnim, file);
      if (existsSync(dst)) continue;
      try {
        copyFileSync(join(srcAnim, file), dst);
        result.copiedFiles += 1;
      } catch (err) {
        log(`复制 ${kind}/${file} 失败：${err.message}`);
      }
    }
  }

  try {
    mkdirSync(PLUGIN_DIR, { recursive: true });
    writeFileSync(
      INSTALL_STATE,
      JSON.stringify({ version: VERSION, at: new Date().toISOString(), ...result }, null, 2) + '\n',
      'utf8',
    );
  } catch {
    /* 状态文件写不了不影响使用 */
  }

  if (result.installed.length) {
    log(`新装 ${result.installed.length} 套（${result.installed.join('、')}），补了 ${result.copiedFiles} 个素材文件`);
    log('pet/ 是新写进去的：dsh-pet 启动时已扫过目录，**重启一次 DSH** 才能在右键里换到新衣服');
  } else if (result.kept.length) {
    log(`四套都在（${result.kept.length} 套保留用户版本）` + (result.copiedFiles ? `，补了 ${result.copiedFiles} 个缺失素材` : ''));
  }
  return result;
}

/** 所有宠物实例：[{ kind, id, name }]，按种类的先后顺序。 */
export function listKinds() {
  const kinds = [];
  const main = readJsonc(MAIN_CONFIG);
  for (const pet of main?.pets ?? []) {
    if (pet && typeof pet.id === 'string' && pet.id) {
      kinds.push({ kind: 'main', id: pet.id, name: pet.name || pet.id, display: pet.display });
    }
  }
  let files = [];
  try {
    files = readdirSync(PET_DIR)
      .filter((f) => /-config\.jsonc?$/.test(f))
      .sort();
  } catch {
    files = [];
  }
  for (const file of files) {
    const kind = file.replace(/-config\.jsonc?$/, '');
    const cfg = readJsonc(join(PET_DIR, file));
    for (const pet of cfg?.pets ?? []) {
      if (pet && typeof pet.id === 'string' && pet.id) {
        kinds.push({ kind, id: pet.id, name: pet.name || pet.id, display: pet.display });
      }
    }
  }
  return kinds;
}

function makeApi(baseUrl) {
  const call = async (path, { method = 'GET', body, timeoutMs = 8000 } = {}) => {
    const res = await fetch(baseUrl + path, {
      method,
      headers: body === undefined ? undefined : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
    const text = await res.text();
    try {
      return JSON.parse(text);
    } catch {
      return { ok: false, raw: text.slice(0, 200) };
    }
  };
  return {
    registerMenu: (labels) =>
      call('/menu/item', { method: 'POST', body: { owner: OWNER, labels, target: 'both' } }),
    readEvents: (wait = 3000) => call(`/menu/events?owner=${encodeURIComponent(OWNER)}&wait=${wait}`),
    setDisplay: (id, display) => call('/pet-display', { method: 'POST', body: { id, display } }),
  };
}

export default {
  name: OWNER,
  apply(root) {
    root.inject(['webServer'], (ctx) => {
      const port = ctx.webServer?.port;
      if (!port) {
        console.warn('[pet-dress] 拿不到 webServer 端口，换装不可用');
        return;
      }
      const baseUrl = `http://127.0.0.1:${port}/dsh-pet-7340`;
      const api = makeApi(baseUrl);
      const log = (s) => console.log('[pet-dress] ' + s);

      let stopped = false;
      ctx.effect(() => () => {
        stopped = true;
      });

      /** dsh-pet 在线吗？用它自己的 /state 探一下，不猜。 */
      const probe = async () => {
        try {
          const res = await fetch(baseUrl + '/state', { signal: AbortSignal.timeout(3000) });
          if (!res.ok) return false;
          JSON.parse(await res.text());
          return true;
        } catch {
          return false;
        }
      };

      const start = () => {
        let entries = []; // [{ label, id, name, all? }]
        const shown = new Set(); // 当前显示着的实例 id（multi 模式用）
        let inited = false;
        const mode = readMode();
        log(`模式：${mode === 'multi' ? 'multi（每只单独开关）' : 'single（换装，互斥）'}`);

        const refresh = () => {
          const kinds = listKinds();
          if (!inited) {
            // 重启后没有内存状态：按各实例配置里的 display 初始化"当前开着"的集合
            shown.clear();
            for (const k of kinds) if (k.display === 'desktop') shown.add(k.id);
            inited = true;
          }
          entries = kinds.map((k) => ({ label: '换装：' + k.name, id: k.id, name: k.name }));
          if (mode === 'multi') {
            // 只有 multi 模式才需要"全部显示"
            entries.push({ label: '换装：全部显示', id: null, name: '全部显示', all: true });
          }
          return kinds;
        };

        const register = async () => {
          refresh();
          if (entries.length === 0) {
            log('没扫到任何宠物实例，跳过注册');
            return false;
          }
          const r = await api.registerMenu(entries.map((e) => e.label));
          if (r && r.ok === true) {
            log('菜单已注册：' + entries.map((e) => e.label).join(' / '));
            return true;
          }
          log('菜单注册失败：' + JSON.stringify(r).slice(0, 160));
          return false;
        };

        /** single：点哪套换哪套（互斥）；multi：点一次 = 这一只的开/关。 */
        const applyKind = async (entry) => {
          const kinds = refresh();
          if (entry.all) {
            // 只有 multi 模式会注册这一项
            let ok = 0;
            for (const k of kinds) {
              const r = await api.setDisplay(k.id, 'desktop');
              if (r && r.ok !== false) {
                shown.add(k.id);
                ok += 1;
              }
            }
            log(`全部显示（${ok}/${kinds.length} 只）`);
            return;
          }
          if (mode === 'multi') {
            const isShown = shown.has(entry.id);
            const r = await api.setDisplay(entry.id, isShown ? 'none' : 'desktop');
            if (r && r.ok !== false) {
              if (isShown) shown.delete(entry.id);
              else shown.add(entry.id);
              log(`${entry.name} -> ${isShown ? '收起' : '显示'}（当前 ${shown.size} 只）`);
            } else {
              log(`${entry.name} 切换失败：` + JSON.stringify(r).slice(0, 120));
            }
            return;
          }
          // single：换装 —— 点哪套，换哪套，其余收起
          let ok = 0;
          for (const k of kinds) {
            const display = k.id === entry.id ? 'desktop' : 'none';
            const r = await api.setDisplay(k.id, display);
            if (r && r.ok !== false) ok += 1;
          }
          shown.clear();
          shown.add(entry.id);
          log(`换装 -> ${entry.name}（${ok}/${kinds.length} 只）`);
        };

        const poll = async () => {
          if (stopped) return;
          try {
            const r = await api.readEvents(3000);
            if (r && r.reason === 'unknown-owner') {
              log('菜单登记丢了，重新注册');
              await register();
            }
            const events = (r && r.ok && r.events) || {};
            for (const [label, petId] of Object.entries(events)) {
              if (typeof petId !== 'string' || petId === '') continue;
              const entry = entries.find((e) => e.label === label);
              if (entry) await applyKind(entry);
            }
          } catch {
            /* 静默：下一轮再试 */
          }
          if (!stopped) setTimeout(poll, 300);
        };

        register()
          .catch((err) => log('注册异常：' + (err && err.message ? err.message : String(err))))
          .finally(() => {
            if (!stopped) poll();
          });
      };

      // 没装 dsh-pet 就什么都不做：不往它的目录写包，也不注册菜单
      probe().then((alive) => {
        if (!alive) {
          log('没检测到 dsh-pet（/dsh-pet-7340/state 不可用）——先把 dsh-pet 装进同一个 profile，pet-dress 才会工作');
          return;
        }
        installPacks(log);
        start();
      });
    });
  },
};
