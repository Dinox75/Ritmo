import {sqliteTable,text,integer,primaryKey,index} from 'drizzle-orm/sqlite-core';
export const accounts=sqliteTable('accounts',{owner:text('owner').primaryKey(),version:integer('version').notNull().default(0),state:text('state').notNull()});
export const requests=sqliteTable('requests',{owner:text('owner').notNull(),id:text('id').notNull(),hash:text('hash').notNull(),version:integer('version').notNull()},t=>[primaryKey({columns:[t.owner,t.id]})]);
export const rates=sqliteTable('rates',{owner:text('owner').notNull(),bucket:text('bucket').notNull(),count:integer('count').notNull(),reset:integer('reset').notNull()},t=>[primaryKey({columns:[t.owner,t.bucket]})]);
export const auditEvents=sqliteTable('audit_events',{
 id:text('id').notNull(),owner:text('owner').notNull(),at:integer('at').notNull(),
 action:text('action').notNull(),result:text('result').notNull(),resource:text('resource').notNull(),
 correlation:text('correlation').notNull(),version:integer('version').notNull()
},t=>[primaryKey({columns:[t.owner,t.id]}),index('audit_owner_time').on(t.owner,t.at,t.id)]);
