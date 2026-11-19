import {sqliteTable,text,integer,primaryKey} from 'drizzle-orm/sqlite-core';
export const accounts=sqliteTable('accounts',{owner:text('owner').primaryKey(),version:integer('version').notNull().default(0),state:text('state').notNull()});
export const requests=sqliteTable('requests',{owner:text('owner').notNull(),id:text('id').notNull(),hash:text('hash').notNull(),version:integer('version').notNull()},t=>[primaryKey({columns:[t.owner,t.id]})]);
export const rates=sqliteTable('rates',{owner:text('owner').notNull(),bucket:text('bucket').notNull(),count:integer('count').notNull(),reset:integer('reset').notNull()},t=>[primaryKey({columns:[t.owner,t.bucket]})]);
