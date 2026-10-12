-- 块 3（10 条）
INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES
('th075', 'Th7.5', '东方萃梦想', 'Immaterial and Missing Power', 'fight', '2004', 'assets/covers/th075.jpg', '萃梦想'),
('th105', 'Th10.5', '东方绯想天', 'Scarlet Weather Rhapsody', 'fight', '2008', 'assets/covers/th105.jpg', '绯想天'),
('th123', 'Th12.3', '东方非想天则', 'Hisoutensoku', 'fight', '2009', 'assets/covers/th123.jpg', '非想天则'),
('th135', 'Th13.5', '东方心绮楼', 'Hopeless Masquerade', 'fight', '2013', 'assets/covers/th135.jpg', '心绮楼'),
('th145', 'Th14.5', '东方深秘录', 'Urban Legend in Limbo', 'fight', '2015', 'assets/covers/th145.jpg', '深秘录'),
('th155', 'Th15.5', '东方凭依华', 'Antinomy of Common Flowers', 'fight', '2017', 'assets/covers/th155.jpg', '凭依华'),
('th095', 'Th9.5', '东方文花帖', 'Shoot the Bullet', 'spin', '2005', 'assets/covers/th095.jpg', '文花帖'),
('th125', 'Th12.5', '东方文花帖DS', 'Double Spoiler', 'spin', '2010', 'assets/covers/th125.jpg', '文花帖DS'),
('th128', 'Th12.8', '妖精大战争', 'Great Fairy Wars', 'spin', '2010', 'assets/covers/th128.jpg', '妖精大战争'),
('th165', 'Th16.5', '秘封噩梦日记', 'Violet Detector', 'spin', '2018', 'assets/covers/th165.jpg', '秘封噩梦日记')
ON CONFLICT (id) DO NOTHING;
