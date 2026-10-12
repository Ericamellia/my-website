-- original_game_categories（5 条）
INSERT INTO original_game_categories (id, label, sort_order) VALUES
('old', '旧作', 0),
('new', '新作', 1),
('fight', '格斗作', 2),
('spin', '外传', 3),
('manga', '官方漫画', 4)
ON CONFLICT (id) DO NOTHING;
