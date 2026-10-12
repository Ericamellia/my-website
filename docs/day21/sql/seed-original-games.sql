-- original_games（39 条）
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

-- 块 4（9 条）
INSERT INTO original_games (id, th, title, subtitle, category, year, cover, tag) VALUES
('th175', 'Th17.5', '东方刚欲异闻', 'Suibotsushita', 'spin', '2021', 'assets/covers/th175.jpg', '刚欲异闻'),
('manga01', '漫画', '东方三月精 ~ Eastern and Little Nature Deity.', '作画：比良坂真琴 · 全1卷', 'manga', '2005–2007', 'assets/covers/manga01.jpg', '三月精'),
('manga02', '漫画', '东方三月精 ~ Strange and Bright Nature Deity.', '作画：比良坂真琴 · 全3卷', 'manga', '2006–2009', 'assets/covers/manga02.jpg', '三月精'),
('manga03', '漫画', '东方三月精 ~ Oriental Sacred Place.', '作画：比良坂真琴 · 全3卷', 'manga', '2009–2012', 'assets/covers/manga03.jpg', '三月精'),
('manga04', '漫画', '东方三月精 ~ Visionary Fairies in Shrine.', '作画：比良坂真琴 · 全3卷', 'manga', '2016–2019', 'assets/covers/manga04.jpg', '三月精'),
('manga05', '漫画', '东方儚月抄 ~ Silent Sinner in Blue.', '作画：秋★枝 · 全3卷', 'manga', '2007–2009', 'assets/covers/manga05.jpg', '儚月抄'),
('manga06', '漫画', '东方儚月抄 ~ 月宫的兔子与地上的兔子', '作画：あらたとしひら · 全2卷', 'manga', '2007–2009', 'assets/covers/manga06.jpg', '儚月抄'),
('manga07', '漫画', '东方茨歌仙 ~ Wild and Horned Hermit.', '作画：あずまあや · 全10卷', 'manga', '2010–2019', 'assets/covers/manga07.jpg', '茨歌仙'),
('manga08', '漫画', '东方铃奈庵 ~ Forbidden Scrollery.', '作画：春河もえ · 全7卷', 'manga', '2012–2017', 'assets/covers/manga08.jpg', '铃奈庵')
ON CONFLICT (id) DO NOTHING;

