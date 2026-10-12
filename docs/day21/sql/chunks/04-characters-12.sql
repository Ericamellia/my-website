-- 块 12（2 条）
INSERT INTO characters (id, name, name_en, games, playable_in, twilight_art, moegirl, source_url) VALUES
('ariya', '磐永阿梨夜', 'Ariya Iwanaga', '{"th20"}'::text[], '{}'::text[], 'assets/characters/ariya.jpg', '{"intro": "东方锦上京第六关的 boss，恒久之姬（石长姬）。掌管永恒，意图将一切化石化以留存。", "basic": {"种族": "神明（石长姬）", "能力": "永恒程度的能力", "称号": "永恒之姬", "登场作品": "东方锦上京"}}'::jsonb, 'https://zh.moegirl.org.cn/磐永阿梨夜'),
('nina', '渡里贝子', 'Nina Watari', '{"th20"}'::text[], '{}'::text[], 'assets/characters/nina.jpg', '{"intro": "东方锦上京 Extra 的 boss，创造虚构都市之怪（双壳贝）。以幻影构筑锦上京的虚像。", "basic": {"种族": "创造虚构都市之怪", "能力": "不明", "称号": "双壳贝上的幻觉", "登场作品": "东方锦上京"}}'::jsonb, 'https://zh.moegirl.org.cn/渡里贝子')
ON CONFLICT (id) DO NOTHING;
