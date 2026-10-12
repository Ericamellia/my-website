-- 块 2（10 条）
INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES
('th11', 'Th11', '东方地灵殿', 'Subterranean Animism', 'new', '2008', 'assets/covers/th11.jpg', '地灵殿'),
('th12', 'Th12', '东方星莲船', 'Undefined Fantastic Object', 'new', '2009', 'assets/covers/th12.jpg', '星莲船'),
('th13', 'Th13', '东方神灵庙', 'Ten Desires', 'new', '2011', 'assets/covers/th13.jpg', '神灵庙'),
('th14', 'Th14', '东方辉针城', 'Double Dealing Character', 'new', '2013', 'assets/covers/th14.jpg', '辉针城'),
('th15', 'Th15', '东方绀珠传', 'Legacy of Lunatic Kingdom', 'new', '2015', 'assets/covers/th15.jpg', '绀珠传'),
('th16', 'Th16', '东方天空璋', 'Hidden Star in Four Seasons', 'new', '2017', 'assets/covers/th16.jpg', '天空璋'),
('th17', 'Th17', '东方鬼形兽', 'Wily Beast and Weakest Creature', 'new', '2019', 'assets/covers/th17.jpg', '鬼形兽'),
('th18', 'Th18', '东方虹龙洞', 'Unconnected Marketeers', 'new', '2021', 'assets/covers/th18.jpg', '虹龙洞'),
('th19', 'Th19', '东方兽王园', 'Unfinished Dream of All Living Ghosts', 'new', '2023', 'assets/covers/th19.jpg', '兽王园'),
('th20', 'Th20', '东方锦上京', 'Fossilized Wonders', 'new', '2025', 'assets/covers/th20.jpg', '锦上京')
ON CONFLICT (id) DO NOTHING;
