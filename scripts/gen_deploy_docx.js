const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
        LevelFormat } = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const T = (t) => new TextRun({ text: t, font: 'Arial', size: 22 });
const TH = (t) => new TextRun({ text: t, font: 'Arial', size: 22, bold: true });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text: t, font: 'Arial', size: 36, bold: true })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 }, children: [new TextRun({ text: t, font: 'Arial', size: 28, bold: true })] });
const P = (...runs) => new Paragraph({ spacing: { after: 120 }, children: runs.flat().map(t => typeof t === 'string' ? T(t) : t) });
const Code = (t) => new Paragraph({ spacing: { after: 80 }, shading: { type: ShadingType.CLEAR, fill: 'F5F5F5' }, indent: { left: 360 }, children: [new TextRun({ text: t, font: 'Consolas', size: 18 })] });
const Bullet = (t) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: [T(t)] });
const empty = () => new Paragraph({ spacing: { after: 80 }, children: [] });

function makeTable(headers, rows) {
  const colW = Math.floor(9026 / headers.length);
  return new Table({
    width: { size: 9026, type: WidthType.DXA },
    columnWidths: headers.map(() => colW),
    rows: [
      new TableRow({ children: headers.map(h => new TableCell({ borders, width: { size: colW, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: 'E8ECF1' }, children: [new Paragraph({ children: [TH(h)] })] })) }),
      ...rows.map(row => new TableRow({ children: row.map(c => new TableCell({ borders, width: { size: colW, type: WidthType.DXA }, children: [new Paragraph({ children: [T(String(c))] })] })) })),
    ]
  });
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 36, bold: true, font: 'Arial' }, paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 28, bold: true, font: 'Arial' }, paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
    ]
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    children: [
      H1('竹条生产管理系统 - 本地部署指南'),
      empty(),
      H2('一、环境要求'),
      makeTable(['软件', '最低版本', '说明'], [
        ['Python', '3.11+', '后端运行环境'],
        ['Node.js', '18+', '前端构建与开发服务器'],
        ['Git', '任意版本', '拉取代码'],
      ]),
      empty(),
      H2('二、获取代码'),
      P('方式一：Git 克隆 (推荐)'),
      Code('git clone https://github.com/lhh666-6/auto-decte.git'),
      Code('cd auto-decte'),
      Code('git checkout modular-architecture'),
      P('方式二：直接下载 (无需安装 Git)'),
      Bullet('浏览器打开 https://github.com/lhh666-6/auto-decte'),
      Bullet('点绿色 Code 按钮 -> Download ZIP'),
      Bullet('下载后解压到任意目录 (如 D:\\auto-decte)'),
      Bullet('后续步骤与 Git 方式完全一致'),
      empty(),

      H2('三、后端部署'),
      P('3.1 创建虚拟环境'),
      Code('python -m venv .venv'),
      P('3.2 激活虚拟环境 (Windows)'),
      Code('.venv\\Scripts\\activate'),
      P('激活虚拟环境 (Linux/macOS)'),
      Code('source .venv/bin/activate'),
      P('3.3 安装依赖'),
      Code('pip install -r requirements.txt'),
      P('3.4 配置环境变量'),
      Code('cp .env.example .env'),
      P('.env 内容 (按需修改)'),
      Code('FORM_DEMO_DATA_ROOT=./data'),
      Code('FORM_DEMO_API_HOST=0.0.0.0'),
      Code('FORM_DEMO_AI_ENABLED=false'),
      Code('APP_AUTH_MODE=local_full_access'),
      P('3.5 初始化数据库'),
      Code('python -m alembic upgrade head'),
      P('3.6 启动后端'),
      Code('python -m uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000'),
      empty(),

      H2('四、前端部署'),
      P('4.1 安装依赖'),
      Code('cd frontend'),
      Code('npm install'),
      P('4.2 启动开发服务器'),
      Code('npm run dev:web'),
      P('默认监听 0.0.0.0:5173，局域网可直接访问。'),
      empty(),

      H2('五、初始管理员账户'),
      makeTable(['工号', '姓名', '角色', 'PIN'], [
        ['ADMIN001', '管理员', '系统管理员', '1234'],
        ['GLY001', '系统管理员', '系统管理员', '2468'],
      ]),
      empty(),

      H2('六、创建其他角色账户'),
      Bullet('浏览器打开 http://localhost:5173'),
      Bullet('用 ADMIN001 / 1234 登录'),
      Bullet('左侧导航 -> 工厂与岗位 -> 新建工厂 (勾选启用业务表单)'),
      Bullet('左侧导航 -> 组织与员工 -> 新增员工'),
      Bullet('选择工厂 -> 选择岗位 -> 填写姓名 -> 设置密码 -> 工号自动生成'),
      empty(),

      H2('七、业务表单预设参数'),
      makeTable(['表单', '名称', '工序'], [
        ['SORTING', '《竹丝装笼跟踪牌》', '分选 -> 主管审核 -> 厂长确认'],
        ['DIPPING_DRYING', '《竹丝浸胶干燥生产记录表》', '浸胶 -> 干燥 -> 主管审核 -> 厂长确认'],
      ]),
      empty(),
      P('分选长度与重量预设：'),
      makeTable(['长度', '每把重量'], [
        ['1.93m', '5 kg'],
        ['2.1m', '5 kg'],
        ['2.35m', '6 kg'],
      ]),
      empty(),

      H2('八、生产环境部署 (可选)'),
      P('后端生产运行：'),
      Code('python -m uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 4'),
      P('前端构建：'),
      Code('cd frontend && npm run build:web'),
      P('构建产物在 frontend/apps/web/dist/，部署到 Nginx 或任意静态文件服务器。'),
      empty(),

      H2('九、局域网访问'),
      makeTable(['服务', '地址'], [
        ['前端', 'http://<本机IP>:5173'],
        ['后端 API', 'http://<本机IP>:8000'],
        ['API 文档', 'http://<本机IP>:8000/docs'],
      ]),
      empty(),

      H2('十、常见问题'),
      P('Q: 启动报 "Path doesn\'t exist: alembic"'),
      P('   A: 在项目根目录执行命令，不要在其他目录启动。'),
      empty(),
      P('Q: 数据库损坏'),
      P('   A: 删除 ./data/database/demo.db，重新执行 alembic upgrade head。'),
      empty(),
      P('Q: 前端端口被占用'),
      P('   A: Vite 会自动尝试下一个端口 (5174、5175...)，按控制台输出的地址访问。'),
      empty(),
      P('Q: crypto.randomUUID 报错'),
      P('   A: 已修复，当前版本使用降级方案兼容非 HTTPS 环境。'),
      empty(),
      P('Q: 如何重置所有数据'),
      P('   A: 删除 data/ 目录，重新运行 alembic upgrade head 即可。'),
      empty(),

      H2('十一、技术栈'),
      makeTable(['层', '技术'], [
        ['后端框架', 'FastAPI (Python)'],
        ['数据库', 'SQLite'],
        ['迁移', 'Alembic'],
        ['前端框架', 'React + TypeScript'],
        ['构建工具', 'Vite'],
        ['测试', 'Vitest (前端) / pytest (后端)'],
      ]),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('DEPLOY.docx', buf);
  console.log('DEPLOY.docx created successfully');
}).catch(err => {
  console.error('Failed:', err.message);
  process.exit(1);
});
