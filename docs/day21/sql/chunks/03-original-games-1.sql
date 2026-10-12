-- 块 1（10 条）
INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES
('th01', 'Th01', '东方灵异传', 'Highly Responsive to Prayers', 'old', '1996', 'assets/covers/th01.jpg', '灵异传'),
('th02', 'Th02', '东方封魔录', 'the Story of Eastern Wonderland', 'old', '1997', 'assets/covers/th02.jpg', '封魔录'),
('th03', 'Th03', '东方梦时空', 'Phantasmagoria of Dim. Dream', 'old', '1997', 'assets/covers/th03.jpg', '梦时空'),
('th04', 'Th04', '东方幻想乡', 'Lotus Land Story', 'old', '1998', 'assets/covers/th04.jpg', '幻想乡'),
('th05', 'Th05', '东方怪绮谈', 'Mystic Square', 'old', '1998', 'assets/covers/th05.jpg', '怪绮谈'),
('th06', 'Th06', '东方红魔乡', 'the Embodiment of Scarlet Devil', 'new', '2002', 'assets/covers/th06.jpg', '红魔乡'),
('th07', 'Th07', '东方妖妖梦', 'Perfect Cherry Blossom', 'new', '2003', 'assets/covers/th07.jpg', '妖妖梦'),
('th08', 'Th08', '东方永夜抄', 'Imperishable Night', 'new', '2004', 'assets/covers/th08.jpg', '永夜抄'),
('th09', 'Th09', '东方花映塚', 'Phantasmagoria of Flower View', 'new', '2005', 'assets/covers/th09.jpg', '花映塚'),
('th10', 'Th10', '东方风神录', 'Mountain of Faith', 'new', '2007', 'assets/covers/th10.jpg', '风神录')
ON CONFLICT (id) DO NOTHING;
